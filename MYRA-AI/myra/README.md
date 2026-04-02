# MYRA Backend

This package adds a modular FastAPI backend for MYRA with:

- Context memory
- User personalization
- Task understanding
- Decision suggestions
- MongoDB persistence

## Structure

```text
myra/
├── api/routes.py
├── app.py
├── core/
├── intelligence/
├── memory/
├── models/
├── services/
├── tasks/
└── user/
```

## Run

```bash
pip install -r myra/requirements.txt
uvicorn myra.app:app --reload
```

## Environment

Copy `myra/.env.example` into your project `.env` and update the values.

## Main APIs

- `POST /api/chat`
- `GET /api/memory?user_id=...&query=...`
- `POST /api/task`
- `GET /api/profile?user_id=...`

## Example Chat Request

```json
{
  "user_id": "user-123",
  "session_id": "session-1",
  "message": "Kal 12 se 2 mera exam hai"
}
```

## Example Response Highlights

- Extracts an `exam` task
- Stores the message in short-term and long-term memory
- Saves a task with reminder metadata
- Updates profile facts when possible
- Returns smart suggestions based on timing and task type
