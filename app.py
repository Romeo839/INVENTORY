from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import csv
import os

app = Flask(__name__)
app.secret_key = "iphone_inventory_secret_2024"

INVENTORY_FILE = "inventory.csv"
USERS_FILE     = "users.csv"
FIELDNAMES     = ["type", "color", "price", "memory", "quantity"]
USER_FIELDS    = ["username", "password", "role", "full_name"]


# ── CSV helpers ──────────────────────────────────────────────────────────────

def read_inventory():
    if not os.path.exists(INVENTORY_FILE):
        return []
    with open(INVENTORY_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_inventory(items):
    with open(INVENTORY_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(items)


def read_users():
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_users(users):
    with open(USERS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=USER_FIELDS)
        writer.writeheader()
        writer.writerows(users)


def find_item(inventory, itype, color, memory):
    for item in inventory:
        if (item["type"].strip().lower()   == itype.strip().lower() and
            item["color"].strip().lower()  == color.strip().lower() and
            item["memory"].strip().lower() == memory.strip().lower()):
            return item
    return None


# ── Auth helpers ─────────────────────────────────────────────────────────────

def logged_in():
    return "username" in session

def is_manager():
    return session.get("role") == "manager"

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not logged_in():
            return jsonify({"success": False, "message": "Not logged in."}), 401
        return f(*args, **kwargs)
    return decorated

def manager_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not logged_in():
            return jsonify({"success": False, "message": "Not logged in."}), 401
        if not is_manager():
            return jsonify({"success": False, "message": "Manager access required."}), 403
        return f(*args, **kwargs)
    return decorated


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if not logged_in():
        return redirect(url_for("login"))
    return render_template("index.html",
                           full_name=session.get("full_name"),
                           role=session.get("role"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    data     = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users    = read_users()
    user     = next((u for u in users if u["username"] == username), None)
    if not user or user["password"] != password:
        return jsonify({"success": False, "message": "Invalid username or password."}), 401
    session["username"]  = user["username"]
    session["role"]      = user["role"]
    session["full_name"] = user["full_name"]
    return jsonify({"success": True, "role": user["role"], "full_name": user["full_name"]})


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Inventory routes ──────────────────────────────────────────────────────────

@app.route("/api/inventory", methods=["GET"])
@login_required
def get_inventory():
    return jsonify(read_inventory())


@app.route("/api/options", methods=["GET"])
@login_required
def get_options():
    inventory = read_inventory()
    tree = {}
    for item in inventory:
        t, c, m = item["type"].strip(), item["color"].strip(), item["memory"].strip()
        if t not in tree:          tree[t] = {}
        if c not in tree[t]:       tree[t][c] = []
        if m not in tree[t][c]:    tree[t][c].append(m)
    return jsonify(tree)


@app.route("/api/restock", methods=["POST"])
@login_required
def restock_item():
    data     = request.json
    itype    = data.get("type", "").strip()
    color    = data.get("color", "").strip()
    memory   = data.get("memory", "").strip()
    quantity = data.get("quantity", "")
    if not all([itype, color, memory, quantity]):
        return jsonify({"success": False, "message": "All fields are required."}), 400
    try:
        quantity = int(quantity)
        if quantity <= 0: raise ValueError
    except ValueError:
        return jsonify({"success": False, "message": "Quantity must be a positive integer."}), 400
    inventory = read_inventory()
    existing  = find_item(inventory, itype, color, memory)
    if not existing:
        return jsonify({"success": False, "message": "Item not found in inventory."}), 404
    existing["quantity"] = str(int(existing["quantity"]) + quantity)
    write_inventory(inventory)
    return jsonify({"success": True, "message": f"Restocked! New quantity: {existing['quantity']}."})


@app.route("/api/add", methods=["POST"])
@manager_required
def add_item():
    data     = request.json
    itype    = data.get("type", "").strip()
    color    = data.get("color", "").strip()
    price    = data.get("price", "").strip()
    memory   = data.get("memory", "").strip()
    quantity = data.get("quantity", "").strip()
    if not all([itype, color, price, memory, quantity]):
        return jsonify({"success": False, "message": "All fields are required."}), 400
    try:
        price    = float(price)
        quantity = int(quantity)
        if price < 0 or quantity <= 0: raise ValueError
    except ValueError:
        return jsonify({"success": False, "message": "Invalid price or quantity."}), 400
    inventory = read_inventory()
    if find_item(inventory, itype, color, memory):
        return jsonify({"success": False, "message": "Item already exists. Use Restock instead."}), 400
    inventory.append({"type": itype, "color": color, "price": str(price), "memory": memory, "quantity": str(quantity)})
    write_inventory(inventory)
    return jsonify({"success": True, "message": f"'{itype} — {color} {memory}' added to inventory!"})


@app.route("/api/remove", methods=["POST"])
@login_required
def remove_item():
    data     = request.json
    itype    = data.get("type", "").strip()
    color    = data.get("color", "").strip()
    memory   = data.get("memory", "").strip()
    quantity = data.get("quantity", "")
    try:
        quantity = int(quantity)
        if quantity <= 0: raise ValueError
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Quantity must be a positive integer."}), 400
    inventory = read_inventory()
    existing  = find_item(inventory, itype, color, memory)
    if not existing:
        return jsonify({"success": False, "message": "Item not found in inventory."}), 404
    current_qty = int(existing["quantity"])
    if quantity > current_qty:
        return jsonify({"success": False, "message": f"Cannot remove {quantity}. Only {current_qty} in stock."}), 400
    new_qty = current_qty - quantity
    if new_qty == 0:
        inventory = [i for i in inventory if not (
            i["type"].strip().lower()   == itype.lower() and
            i["color"].strip().lower()  == color.lower() and
            i["memory"].strip().lower() == memory.lower())]
    else:
        existing["quantity"] = str(new_qty)
    write_inventory(inventory)
    msg = "All units removed. Item deleted." if new_qty == 0 else f"Removed {quantity} unit(s). Remaining: {new_qty}."
    return jsonify({"success": True, "message": msg})


@app.route("/api/update_price", methods=["POST"])
@manager_required
def update_price():
    data      = request.json
    itype     = data.get("type", "").strip()
    color     = data.get("color", "").strip()
    memory    = data.get("memory", "").strip()
    new_price = data.get("price", "").strip()
    try:
        new_price = float(new_price)
        if new_price < 0: raise ValueError
    except ValueError:
        return jsonify({"success": False, "message": "Invalid price."}), 400
    inventory = read_inventory()
    existing  = find_item(inventory, itype, color, memory)
    if not existing:
        return jsonify({"success": False, "message": "Item not found in inventory."}), 404
    old_price = existing["price"]
    existing["price"] = str(new_price)
    write_inventory(inventory)
    return jsonify({"success": True, "message": f"Price updated from ${float(old_price):.2f} to ${new_price:.2f}."})


# ── Staff management routes (manager only) ────────────────────────────────────

@app.route("/api/staff", methods=["GET"])
@manager_required
def get_staff():
    users = read_users()
    # Never expose passwords to frontend
    safe  = [{"username": u["username"], "full_name": u["full_name"], "role": u["role"]} for u in users]
    return jsonify(safe)


@app.route("/api/staff/add", methods=["POST"])
@manager_required
def add_staff():
    data      = request.json
    username  = data.get("username", "").strip()
    password  = data.get("password", "").strip()
    role      = data.get("role", "employee").strip()
    full_name = data.get("full_name", "").strip()
    if not all([username, password, full_name]):
        return jsonify({"success": False, "message": "All fields are required."}), 400
    if role not in ["manager", "employee"]:
        return jsonify({"success": False, "message": "Role must be manager or employee."}), 400
    users = read_users()
    if any(u["username"] == username for u in users):
        return jsonify({"success": False, "message": "Username already exists."}), 400
    users.append({"username": username, "password": password, "role": role, "full_name": full_name})
    write_users(users)
    return jsonify({"success": True, "message": f"{full_name} added as {role}."})


@app.route("/api/staff/promote", methods=["POST"])
@manager_required
def promote_staff():
    data     = request.json
    username = data.get("username", "").strip()
    new_role = data.get("role", "").strip()
    if new_role not in ["manager", "employee"]:
        return jsonify({"success": False, "message": "Role must be manager or employee."}), 400
    users = read_users()
    user  = next((u for u in users if u["username"] == username), None)
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404
    if username == session.get("username"):
        return jsonify({"success": False, "message": "You cannot change your own role."}), 400
    old_role      = user["role"]
    user["role"]  = new_role
    write_users(users)
    return jsonify({"success": True, "message": f"{user['full_name']} changed from {old_role} to {new_role}."})


@app.route("/api/staff/change_password", methods=["POST"])
@login_required
def change_password():
    data         = request.json
    old_password = data.get("old_password", "").strip()
    new_password = data.get("new_password", "").strip()
    if not old_password or not new_password:
        return jsonify({"success": False, "message": "Both fields are required."}), 400
    if len(new_password) < 6:
        return jsonify({"success": False, "message": "New password must be at least 6 characters."}), 400
    users    = read_users()
    username = session.get("username")
    user     = next((u for u in users if u["username"] == username), None)
    if not user or user["password"] != old_password:
        return jsonify({"success": False, "message": "Current password is incorrect."}), 401
    user["password"] = new_password
    write_users(users)
    return jsonify({"success": True, "message": "Password updated successfully."})


if __name__ == "__main__":
    app.run(debug=True)
