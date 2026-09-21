# Postman API Guide — SupportAI Backend

Base URL: `http://localhost:8000`

Swagger UI: http://localhost:8000/api/docs/

সব POST request-এ Header:

```
Content-Type: application/json
```

Protected endpoint-এ (`/api/me/...`):

```
Authorization: Bearer <access_token>
```

---

## 1. Register (Customer create)

Register API শুধু **customer** role-এ user তৈরি করে।

**POST** `/api/auth/register/`

```json
{
  "name": "Rahim Ahmed",
  "email": "rahim@example.com",
  "password": "demo1234"
}
```

আরেকটা customer:

```json
{
  "name": "Karim Hassan",
  "email": "karim@example.com",
  "password": "demo1234"
}
```

**Response (201):** `user` object + `tokens.access` + `tokens.refresh`

---

## 2. Login

**POST** `/api/auth/login/`

Customer:

```json
{
  "email": "rahim@example.com",
  "password": "demo1234"
}
```

Agent (shell/admin দিয়ে তৈরি করার পর):

```json
{
  "email": "sara@company.com",
  "password": "demo1234"
}
```

Admin (shell/admin দিয়ে তৈরি করার পর):

```json
{
  "email": "admin@company.com",
  "password": "demo1234"
}
```

**Response (200):** `user` object + `tokens.access` + `tokens.refresh`

---

## 3. Token Refresh

**POST** `/api/auth/refresh/`

```json
{
  "refresh": "PASTE_REFRESH_TOKEN_HERE"
}
```

---

## 4. Current User Profile

**GET** `/api/me/auth/me/`

Header:

```
Authorization: Bearer PASTE_ACCESS_TOKEN_HERE
```

---

## 5. Create Ticket (Customer)

Customer হিসেবে login করে access token নিন, তারপর:

**POST** `/api/me/tickets/`

Header:

```
Authorization: Bearer PASTE_ACCESS_TOKEN_HERE
Content-Type: application/json
```

Body:

```json
{
  "subject": "Cannot reset my password",
  "description": "I tried resetting my password but the email never arrives."
}
```

---

## Agent / Admin create (API নেই)

Register endpoint দিয়ে agent/admin তৈরি হয় না। নিচের যেকোনো একটি উপায় ব্যবহার করুন।

### Option A — Django superuser + Admin panel

```bash
cd backend
docker compose exec web python manage.py createsuperuser
```

Browser: http://localhost:8000/admin/ → **Users** → Add user → role `agent` বা `admin` set করুন।

### Option B — Django shell

```bash
docker compose exec web python manage.py shell
```

```python
from accountssu.models import User

# Agent
agent = User.objects.create_user(
    username="sara@company.com",
    email="sara@company.com",
    password="demo1234",
    first_name="Sara",
    last_name="Khan",
    role="agent",
    max_open_tickets=10,
    is_available=True,
)

# Admin
User.objects.create_user(
    username="admin@company.com",
    email="admin@company.com",
    password="demo1234",
    first_name="Admin",
    last_name="User",
    role="admin",
    is_staff=True,
    is_superuser=True,
)
```

---

## Postman workflow

1. **Register** বা **Login** → response থেকে `tokens.access` copy করুন
2. Postman **Authorization** tab → Type: **Bearer Token** → token paste
3. `/api/me/` endpoints test করুন

---

## Database connection (DBeaver / pgAdmin)

| Field    | Value       |
|----------|-------------|
| Host     | `localhost` |
| Port     | `5433`      |
| Database | `supportai` |
| User     | `postgres`  |
| Password | `postgres`  |

> Database field-এ অবশ্যই `supportai` দিন — খালি রাখলে table দেখা যাবে না।

---

## Related docs

- Backend README: [README.md](./README.md)
- Swagger: http://localhost:8000/api/docs/
- ReDoc: http://localhost:8000/api/redoc/
