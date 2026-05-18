from fastapi import FastAPI, HTTPException, Depends, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import os
import bcrypt

from database import get_db_connection

SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

app = FastAPI(title="ИС Обработки Заявок")
templates = Jinja2Templates(directory="templates")

def create_access_token(data: dict):
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.*, r.role_name FROM users u
            JOIN roles r ON u.role_id = r.role_id
            WHERE u.user_id = %s AND u.is_active = TRUE
        """, (user_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return user
    except JWTError:
        return None

def generate_request_number(conn):
    cur = conn.cursor()
    cur.execute("SELECT MAX(request_number) as max_num FROM requests")
    max_num = cur.fetchone()['max_num']
    num = int(max_num.split('-')[-1]) + 1 if max_num else 1
    return f"REQ-{datetime.now().strftime('%Y%m')}-{num:04d}"

# ========== СТРАНИЦЫ ==========
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    return RedirectResponse(url="/dashboard")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.*, r.role_name FROM users u
        JOIN roles r ON u.role_id = r.role_id
        WHERE u.email = %s AND u.is_active = TRUE
    """, (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Неверный email или пароль"})
    
    token = create_access_token(data={"sub": str(user['user_id'])})
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(key="access_token", value=token, httponly=True)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as total FROM requests")
    total = cur.fetchone()['total']
    cur.execute("SELECT COUNT(*) as new FROM requests WHERE status_id = 1")
    new = cur.fetchone()['new']
    cur.execute("SELECT COUNT(*) as inwork FROM requests WHERE status_id IN (2,3)")
    inwork = cur.fetchone()['inwork']
    cur.close()
    conn.close()
    
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "stats": {"total": total, "new": new, "inwork": inwork}})

@app.get("/requests", response_class=HTMLResponse)
async def requests_list(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("requests.html", {"request": request, "user": user})

@app.get("/requests/new", response_class=HTMLResponse)
async def new_request_form(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT category_id, category_name FROM categories")
    categories = cur.fetchall()
    cur.execute("SELECT priority_id, priority_name FROM priorities")
    priorities = cur.fetchall()
    cur.close()
    conn.close()
    return templates.TemplateResponse("request_form.html", {"request": request, "user": user, "categories": categories, "priorities": priorities})

@app.get("/requests/{request_id}", response_class=HTMLResponse)
async def request_card(request: Request, request_id: int):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("request_card.html", {"request": request, "user": user, "request_id": request_id})

# ========== API ==========
from pydantic import BaseModel

class RequestCreate(BaseModel):
    title: str
    description: str
    category_id: int
    priority_id: int

@app.post("/api/requests")
async def create_request(data: RequestCreate, request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    
    conn = get_db_connection()
    cur = conn.cursor()
    request_number = generate_request_number(conn)
    
    cur.execute("""
        INSERT INTO requests (request_number, created_by, title, description, category_id, priority_id, status_id)
        VALUES (%s, %s, %s, %s, %s, %s, 1) RETURNING request_id
    """, (request_number, user['user_id'], data.title, data.description, data.category_id, data.priority_id))
    new_id = cur.fetchone()['request_id']
    cur.execute("INSERT INTO request_history (request_id, changed_by, new_status_id, change_note) VALUES (%s, %s, 1, 'Заявка создана')", (new_id, user['user_id']))
    conn.commit()
    cur.close()
    conn.close()
    return {"request_id": new_id, "request_number": request_number}

@app.get("/api/requests")
async def get_requests(request: Request, status_id: Optional[int] = None):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    
    conn = get_db_connection()
    cur = conn.cursor()
    sql = """
        SELECT r.request_id, r.request_number, r.created_at, r.title,
               c.category_name, p.priority_name, s.status_name, u.full_name as executor_name
        FROM requests r
        JOIN categories c ON r.category_id = c.category_id
        JOIN priorities p ON r.priority_id = p.priority_id
        JOIN statuses s ON r.status_id = s.status_id
        LEFT JOIN users u ON r.assigned_to = u.user_id
        WHERE 1=1
    """
    params = []
    if status_id:
        sql += " AND r.status_id = %s"
        params.append(status_id)
    if user['role_name'] == 'Заявитель':
        sql += " AND r.created_by = %s"
        params.append(user['user_id'])
    elif user['role_name'] == 'Исполнитель':
        sql += " AND (r.assigned_to = %s OR r.created_by = %s)"
        params.extend([user['user_id'], user['user_id']])
    
    sql += " ORDER BY r.created_at DESC"
    cur.execute(sql, params)
    items = cur.fetchall()
    cur.close()
    conn.close()
    return items

@app.get("/api/requests/{request_id}")
async def get_request_detail(request_id: int, req: Request):
    user = await get_current_user(req)
    if not user:
        raise HTTPException(status_code=401)
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.*, c.category_name, p.priority_name, s.status_name,
               creator.full_name as creator_name, executor.full_name as executor_name
        FROM requests r
        JOIN categories c ON r.category_id = c.category_id
        JOIN priorities p ON r.priority_id = p.priority_id
        JOIN statuses s ON r.status_id = s.status_id
        JOIN users creator ON r.created_by = creator.user_id
        LEFT JOIN users executor ON r.assigned_to = executor.user_id
        WHERE r.request_id = %s
    """, (request_id,))
    request_data = cur.fetchone()
    
    cur.execute("SELECT h.*, u.full_name FROM request_history h JOIN users u ON h.changed_by = u.user_id WHERE h.request_id = %s ORDER BY h.changed_at", (request_id,))
    history = cur.fetchall()
    cur.execute("SELECT c.*, u.full_name FROM request_comments c JOIN users u ON c.author_id = u.user_id WHERE c.request_id = %s ORDER BY c.created_at", (request_id,))
    comments = cur.fetchall()
    cur.execute("SELECT status_id, status_name FROM statuses ORDER BY sort_order")
    statuses = cur.fetchall()
    cur.execute("SELECT user_id, full_name FROM users WHERE role_id = (SELECT role_id FROM roles WHERE role_name='Исполнитель') AND is_active = TRUE")
    executors = cur.fetchall()
    
    cur.close()
    conn.close()
    return {"request": request_data, "history": history, "comments": comments, "statuses": statuses, "executors": executors}

@app.patch("/api/requests/{request_id}/status")
async def change_status(request_id: int, new_status_id: int, note: str = "", req: Request):
    user = await get_current_user(req)
    if not user:
        raise HTTPException(status_code=401)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status_id FROM requests WHERE request_id = %s", (request_id,))
    old = cur.fetchone()
    if not old:
        raise HTTPException(status_code=404)
    cur.execute("UPDATE requests SET status_id = %s WHERE request_id = %s", (new_status_id, request_id))
    cur.execute("INSERT INTO request_history (request_id, changed_by, old_status_id, new_status_id, change_note) VALUES (%s, %s, %s, %s, %s)",
                (request_id, user['user_id'], old['status_id'], new_status_id, note or "Изменение статуса"))
    conn.commit()
    cur.close()
    conn.close()
    return {"success": True}

@app.patch("/api/requests/{request_id}/assign")
async def assign_executor(request_id: int, executor_id: int, req: Request):
    user = await get_current_user(req)
    if not user or user['role_name'] != 'Администратор':
        raise HTTPException(status_code=403)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE requests SET assigned_to = %s WHERE request_id = %s", (executor_id, request_id))
    cur.execute("INSERT INTO request_history (request_id, changed_by, change_note) VALUES (%s, %s, %s)",
                (request_id, user['user_id'], f"Назначен исполнитель ID:{executor_id}"))
    conn.commit()
    cur.close()
    conn.close()
    return {"success": True}

@app.post("/api/requests/{request_id}/comments")
async def add_comment(request_id: int, comment_text: str, req: Request):
    user = await get_current_user(req)
    if not user:
        raise HTTPException(status_code=401)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO request_comments (request_id, author_id, comment_text) VALUES (%s, %s, %s)",
                (request_id, user['user_id'], comment_text))
    conn.commit()
    cur.close()
    conn.close()
    return {"success": True}