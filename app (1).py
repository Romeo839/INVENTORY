from flask import Flask, render_template, request, jsonify
import csv
import os

app = Flask(__name__)

INVENTORY_FILE = "inventory.csv"
FIELDNAMES = ["type", "color", "price", "memory", "quantity"]


def read_inventory():
    if not os.path.exists(INVENTORY_FILE):
        return []
    with open(INVENTORY_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_inventory(items):
    with open(INVENTORY_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(items)


def find_item(inventory, itype, color, memory):
    for item in inventory:
        if (
            item["type"].strip().lower() == itype.strip().lower()
            and item["color"].strip().lower() == color.strip().lower()
            and item["memory"].strip().lower() == memory.strip().lower()
        ):
            return item
    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/inventory", methods=["GET"])
def get_inventory():
    inventory = read_inventory()
    return jsonify(inventory)


# Returns chained dropdown data built from the CSV
@app.route("/api/options", methods=["GET"])
def get_options():
    inventory = read_inventory()
    tree = {}
    for item in inventory:
        t = item["type"].strip()
        c = item["color"].strip()
        m = item["memory"].strip()
        if t not in tree:
            tree[t] = {}
        if c not in tree[t]:
            tree[t][c] = []
        if m not in tree[t][c]:
            tree[t][c].append(m)
    return jsonify(tree)


@app.route("/api/restock", methods=["POST"])
def restock_item():
    """Increase quantity of an existing item selected from dropdowns."""
    data = request.json
    itype = data.get("type", "").strip()
    color = data.get("color", "").strip()
    memory = data.get("memory", "").strip()
    quantity = data.get("quantity", "")

    if not all([itype, color, memory, quantity]):
        return jsonify({"success": False, "message": "All fields are required."}), 400

    try:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValueError
    except ValueError:
        return jsonify({"success": False, "message": "Quantity must be a positive integer."}), 400

    inventory = read_inventory()
    existing = find_item(inventory, itype, color, memory)

    if not existing:
        return jsonify({"success": False, "message": "Item not found in inventory."}), 404

    existing["quantity"] = str(int(existing["quantity"]) + quantity)
    write_inventory(inventory)
    return jsonify({"success": True, "message": f"Restocked! New quantity: {existing['quantity']}."})


@app.route("/api/add", methods=["POST"])
def add_item():
    """Add a brand new item not yet in the CSV."""
    data = request.json
    itype = data.get("type", "").strip()
    color = data.get("color", "").strip()
    price = data.get("price", "").strip()
    memory = data.get("memory", "").strip()
    quantity = data.get("quantity", "").strip()

    if not all([itype, color, price, memory, quantity]):
        return jsonify({"success": False, "message": "All fields are required."}), 400

    try:
        price = float(price)
        quantity = int(quantity)
        if price < 0 or quantity <= 0:
            raise ValueError
    except ValueError:
        return jsonify({"success": False, "message": "Price must be a positive number and quantity a positive integer."}), 400

    inventory = read_inventory()
    existing = find_item(inventory, itype, color, memory)

    if existing:
        return jsonify({"success": False, "message": "This item already exists. Use the Restock tab instead."}), 400

    new_item = {
        "type": itype,
        "color": color,
        "price": str(price),
        "memory": memory,
        "quantity": str(quantity),
    }
    inventory.append(new_item)
    write_inventory(inventory)
    return jsonify({"success": True, "message": f"'{itype} — {color} {memory}' added to inventory!"})


@app.route("/api/remove", methods=["POST"])
def remove_item():
    data = request.json
    itype = data.get("type", "").strip()
    color = data.get("color", "").strip()
    memory = data.get("memory", "").strip()
    quantity = data.get("quantity", "")

    try:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Quantity must be a positive integer."}), 400

    inventory = read_inventory()
    existing = find_item(inventory, itype, color, memory)

    if not existing:
        return jsonify({"success": False, "message": "Item not found in inventory."}), 404

    current_qty = int(existing["quantity"])
    if quantity > current_qty:
        return jsonify({"success": False, "message": f"Cannot remove {quantity}. Only {current_qty} in stock."}), 400

    new_qty = current_qty - quantity
    if new_qty == 0:
        inventory = [i for i in inventory if not (
            i["type"].strip().lower() == itype.lower() and
            i["color"].strip().lower() == color.lower() and
            i["memory"].strip().lower() == memory.lower()
        )]
        write_inventory(inventory)
        return jsonify({"success": True, "message": "All units removed. Item deleted from inventory."})
    else:
        existing["quantity"] = str(new_qty)
        write_inventory(inventory)
        return jsonify({"success": True, "message": f"Removed {quantity} unit(s). Remaining: {new_qty}."})


@app.route("/api/update_price", methods=["POST"])
def update_price():
    data = request.json
    itype = data.get("type", "").strip()
    color = data.get("color", "").strip()
    memory = data.get("memory", "").strip()
    new_price = data.get("price", "").strip()

    try:
        new_price = float(new_price)
        if new_price < 0:
            raise ValueError
    except ValueError:
        return jsonify({"success": False, "message": "Invalid price."}), 400

    inventory = read_inventory()
    existing = find_item(inventory, itype, color, memory)

    if not existing:
        return jsonify({"success": False, "message": "Item not found in inventory."}), 404

    old_price = existing["price"]
    existing["price"] = str(new_price)
    write_inventory(inventory)
    return jsonify({"success": True, "message": f"Price updated from ${float(old_price):.2f} to ${new_price:.2f}."})


if __name__ == "__main__":
    app.run(debug=True)
