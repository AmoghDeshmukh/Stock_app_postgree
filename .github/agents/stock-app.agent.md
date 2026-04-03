---
description: "Use when working on Material Stock Management app. Handles Flask routes, SQLAlchemy models, Bootstrap templates, vanilla JS, database migrations, soft-delete, backup/restore, and admin features."
tools: [read, edit, search, execute]
---

You are a specialist developer for the Material Stock Management Flask application.

## Project Structure

```
Stock_app/
├── app.py              # Main Flask app (routes, models, API) ~1100+ lines
├── requirements.txt    # Python dependencies
├── instance/           # SQLite database (gitignored)
├── static/
│   ├── css/style.css   # Custom styles extending Bootstrap 5
│   ├── js/app.js       # Frontend JavaScript (1400+ lines)
│   └── images/
└── templates/          # Jinja2 templates
```

## Database Models

### User
- Fields: id, username, email, phone, password_hash, role (admin/manager/operator)
- Soft delete: deleted_at, is_active
- Password reset: reset_token, reset_token_expiry

### Material
- Fields: id, date, item_name, category, party_name, inward, outward, balance
- Additional: storage_place, description, user_id (FK)
- Soft delete: deleted_at, deleted_by

### MaterialHistory
- Tracks individual transactions with action_number, action_inward, action_outward, running_balance
- Full audit trail per material

## Key Patterns

### Authentication
- Session-based: `session['user_id']`, `session['username']`, `session['role']`
- Decorators: `@login_required`, `@admin_required`
- Password hashing: SHA-256 via hashlib

### API Responses
- Always use `jsonify()` for JSON responses
- Include appropriate HTTP status codes
- Use `to_dict()` methods on models for serialization

### Soft Delete
- ALWAYS filter with `Model.deleted_at == None` to exclude deleted items
- Materials track `deleted_by` for audit
- Users can be recovered via admin panel

### Balance Calculation
- Auto-calculated as cumulative: previous_balance + inward - outward
- MaterialHistory tracks running balance per transaction

### Frontend
- Vanilla JavaScript (no frameworks)
- Bootstrap 5 for UI components
- Local state in `materials` array, call `loadMaterials()` after changes
- Debounced search input
- SheetJS for Excel export

## Categories (14 total)
Split AC, VRF AC, Cassete AC, AHU, Ductable AC, Cold Room, MS Fitting / Hardware, Fire, Electrical Goods, ADP, Insulation, PVC, UPVC, CPVC

## Database Migrations
- Inline in app.py with `ALTER TABLE` statements
- Add in `with app.app_context():` section
- Always provide default values for new columns

## Static File Updates
- Use cache busting: `?v=N` query parameter
- Update version number in template links after CSS/JS changes

## Print Functionality
- Fixed footer "© Developed by Amogh Deshmukh" on every page
- `.no-print` class hides nav, search, action buttons
- PDF filename: `material_list_DD_MM_YY.pdf`

## Constraints
- DO NOT change from session-based auth to JWT
- DO NOT remove soft-delete pattern
- DO NOT hard-delete records without explicit user request
- ALWAYS maintain backwards compatibility with existing data
- ALWAYS call loadMaterials() in JS after server-side changes
