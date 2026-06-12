from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
import json
import mimetypes
import os
import re
import threading
import time
import uuid


ROOT_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT_DIR / "src"
DATA_DIR = ROOT_DIR / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"
STORE_FILE = DATA_DIR / "store.json"
PORT = int(os.environ.get("PORT", "3000"))
MAX_BODY_SIZE = 1_000_000
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

DATA_LOCK = threading.Lock()


class ApiError(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def ensure_data_files():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not STORE_FILE.exists():
        write_json(STORE_FILE, {"carts": {}, "newsletter": [], "orders": []})


def read_json(file_path, fallback):
    if not file_path.exists():
        return fallback

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(file_path, payload):
    with file_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def normalize_store(store):
    return {
        "carts": store.get("carts") if isinstance(store.get("carts"), dict) else {},
        "newsletter": store.get("newsletter") if isinstance(store.get("newsletter"), list) else [],
        "orders": store.get("orders") if isinstance(store.get("orders"), list) else [],
    }


def read_store():
    return normalize_store(read_json(STORE_FILE, {"carts": {}, "newsletter": [], "orders": []}))


def save_store(store):
    write_json(STORE_FILE, normalize_store(store))


def read_products():
    products = read_json(PRODUCTS_FILE, [])

    if not isinstance(products, list):
        raise ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, "O catálogo de produtos está inválido.")

    return products


def save_products(products):
    write_json(PRODUCTS_FILE, products)


def find_product(products, product_id):
    return next((product for product in products if product.get("id") == product_id), None)


def normalize_email(email):
    return str(email or "").strip().lower()


def validate_email(email):
    return bool(EMAIL_PATTERN.match(email))


def parse_quantity(value):
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        raise ApiError(HTTPStatus.BAD_REQUEST, "Informe uma quantidade válida.")

    if quantity < 0:
        raise ApiError(HTTPStatus.BAD_REQUEST, "Informe uma quantidade válida.")

    return quantity


def create_session_cart(store, session_id=None):
    session_id = str(session_id or "").strip() or str(uuid.uuid4())
    carts = store["carts"]

    if session_id not in carts:
        now = current_timestamp()
        carts[session_id] = {
            "sessionId": session_id,
            "items": [],
            "createdAt": now,
            "updatedAt": now,
        }

    return carts[session_id]


def current_timestamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_cart_response(cart, products):
    items = []

    for item in cart.get("items", []):
        product = find_product(products, item.get("productId"))
        if not product:
            continue

        quantity = int(item.get("quantity", 0))
        line_total = int(product["priceCents"]) * quantity
        items.append({
            "product": product,
            "quantity": quantity,
            "lineTotalCents": line_total,
        })

    totals = {
        "totalQuantity": sum(item["quantity"] for item in items),
        "subtotalCents": sum(item["lineTotalCents"] for item in items),
    }

    return {"items": items, "totals": totals}


def create_order_id():
    return f"NOCT-{int(time.time() * 1000):X}"


class NocturnaHandler(BaseHTTPRequestHandler):
    server_version = "NocturnaAtelier/1.0"

    def do_OPTIONS(self):
        self.send_json(HTTPStatus.NO_CONTENT, {})

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def do_PATCH(self):
        self.handle_request()

    def do_DELETE(self):
        self.handle_request()

    def handle_request(self):
        try:
            parsed_url = urlparse(self.path)

            if parsed_url.path.startswith("/api/"):
                self.route_api(parsed_url)
            else:
                self.serve_static(parsed_url.path)
        except ApiError as error:
            self.send_json(error.status_code, {"message": error.message})
        except Exception as error:
            print(error)
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"message": "Erro interno do servidor."})

    def route_api(self, parsed_url):
        path = parsed_url.path
        method = self.command

        if path == "/api/health" and method == "GET":
            self.send_json(HTTPStatus.OK, {"ok": True, "service": "Nocturna Atelier API"})
            return

        if path == "/api/products" and method == "GET":
            with DATA_LOCK:
                self.send_json(HTTPStatus.OK, {"products": read_products()})
            return

        product_match = re.match(r"^/api/products/([^/]+)$", path)
        if product_match and method == "GET":
            product_id = unquote(product_match.group(1))
            with DATA_LOCK:
                product = find_product(read_products(), product_id)

            if not product:
                raise ApiError(HTTPStatus.NOT_FOUND, "Produto não encontrado.")

            self.send_json(HTTPStatus.OK, {"product": product})
            return

        if path == "/api/cart" and method == "GET":
            query = parse_qs(parsed_url.query)
            session_id = query.get("sessionId", [None])[0]
            self.handle_get_cart(session_id)
            return

        if path == "/api/cart/items" and method == "POST":
            self.handle_add_cart_item()
            return

        cart_item_match = re.match(r"^/api/cart/items/([^/]+)$", path)
        if cart_item_match and method == "PATCH":
            self.handle_update_cart_item(unquote(cart_item_match.group(1)))
            return

        if cart_item_match and method == "DELETE":
            self.handle_remove_cart_item(unquote(cart_item_match.group(1)))
            return

        if path == "/api/newsletter" and method == "POST":
            self.handle_newsletter()
            return

        if path == "/api/orders" and method == "POST":
            self.handle_create_order()
            return

        order_match = re.match(r"^/api/orders/([^/]+)$", path)
        if order_match and method == "GET":
            self.handle_get_order(unquote(order_match.group(1)))
            return

        raise ApiError(HTTPStatus.NOT_FOUND, "Rota não encontrada.")

    def handle_get_cart(self, session_id):
        with DATA_LOCK:
            store = read_store()
            products = read_products()
            cart = create_session_cart(store, session_id)
            save_store(store)

        self.send_json(HTTPStatus.OK, {
            "sessionId": cart["sessionId"],
            "cart": build_cart_response(cart, products),
        })

    def handle_add_cart_item(self):
        body = self.read_body()
        product_id = str(body.get("productId", "")).strip()
        quantity = parse_quantity(body.get("quantity", 1))

        if not product_id or quantity == 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Informe o produto e a quantidade.")

        with DATA_LOCK:
            store = read_store()
            products = read_products()
            product = find_product(products, product_id)

            if not product:
                raise ApiError(HTTPStatus.NOT_FOUND, "Produto não encontrado.")

            cart = create_session_cart(store, body.get("sessionId"))
            existing_item = next(
                (item for item in cart["items"] if item.get("productId") == product_id),
                None,
            )
            next_quantity = int(existing_item.get("quantity", 0)) + quantity if existing_item else quantity

            if next_quantity > int(product["stock"]):
                raise ApiError(HTTPStatus.CONFLICT, "Estoque insuficiente para esta peça.")

            if existing_item:
                existing_item["quantity"] = next_quantity
            else:
                cart["items"].append({"productId": product_id, "quantity": quantity})

            cart["updatedAt"] = current_timestamp()
            save_store(store)

        self.send_json(HTTPStatus.OK, {
            "sessionId": cart["sessionId"],
            "cart": build_cart_response(cart, products),
        })

    def handle_update_cart_item(self, product_id):
        body = self.read_body()
        quantity = parse_quantity(body.get("quantity"))

        with DATA_LOCK:
            store = read_store()
            products = read_products()
            product = find_product(products, product_id)

            if not product:
                raise ApiError(HTTPStatus.NOT_FOUND, "Produto não encontrado.")

            if quantity > int(product["stock"]):
                raise ApiError(HTTPStatus.CONFLICT, "Estoque insuficiente para esta peça.")

            cart = create_session_cart(store, body.get("sessionId"))
            existing_item = next(
                (item for item in cart["items"] if item.get("productId") == product_id),
                None,
            )

            if quantity == 0:
                cart["items"] = [item for item in cart["items"] if item.get("productId") != product_id]
            elif existing_item:
                existing_item["quantity"] = quantity
            else:
                cart["items"].append({"productId": product_id, "quantity": quantity})

            cart["updatedAt"] = current_timestamp()
            save_store(store)

        self.send_json(HTTPStatus.OK, {
            "sessionId": cart["sessionId"],
            "cart": build_cart_response(cart, products),
        })

    def handle_remove_cart_item(self, product_id):
        body = self.read_body()

        with DATA_LOCK:
            store = read_store()
            products = read_products()
            cart = create_session_cart(store, body.get("sessionId"))
            cart["items"] = [item for item in cart["items"] if item.get("productId") != product_id]
            cart["updatedAt"] = current_timestamp()
            save_store(store)

        self.send_json(HTTPStatus.OK, {
            "sessionId": cart["sessionId"],
            "cart": build_cart_response(cart, products),
        })

    def handle_newsletter(self):
        body = self.read_body()
        email = normalize_email(body.get("email"))

        if not validate_email(email):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Informe um e-mail válido.")

        with DATA_LOCK:
            store = read_store()
            already_registered = any(lead.get("email") == email for lead in store["newsletter"])

            if not already_registered:
                store["newsletter"].append({
                    "id": str(uuid.uuid4()),
                    "email": email,
                    "createdAt": current_timestamp(),
                })
                save_store(store)

        self.send_json(HTTPStatus.CREATED, {
            "message": "Este e-mail já está na lista privada."
            if already_registered
            else "Cadastro realizado com sucesso.",
        })

    def handle_create_order(self):
        body = self.read_body()
        customer = body.get("customer") if isinstance(body.get("customer"), dict) else {}
        customer_name = str(customer.get("name", "")).strip()
        customer_email = normalize_email(customer.get("email"))

        if len(customer_name) < 2:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Informe o nome para finalizar o pedido.")

        if not validate_email(customer_email):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Informe um e-mail válido para o pedido.")

        with DATA_LOCK:
            store = read_store()
            products = read_products()
            cart = create_session_cart(store, body.get("sessionId"))

            if not cart["items"]:
                raise ApiError(HTTPStatus.BAD_REQUEST, "A sacola está vazia.")

            order_items = []

            for item in cart["items"]:
                product = find_product(products, item.get("productId"))
                quantity = int(item.get("quantity", 0))

                if not product:
                    raise ApiError(
                        HTTPStatus.NOT_FOUND,
                        "Uma das peças da sacola não está mais disponível.",
                    )

                if quantity > int(product["stock"]):
                    raise ApiError(HTTPStatus.CONFLICT, f"Estoque insuficiente para {product['name']}.")

                order_items.append({
                    "productId": product["id"],
                    "name": product["name"],
                    "category": product["category"],
                    "priceCents": int(product["priceCents"]),
                    "quantity": quantity,
                    "lineTotalCents": int(product["priceCents"]) * quantity,
                })

            order = {
                "id": create_order_id(),
                "customer": {"name": customer_name, "email": customer_email},
                "items": order_items,
                "totals": {
                    "totalQuantity": sum(item["quantity"] for item in order_items),
                    "subtotalCents": sum(item["lineTotalCents"] for item in order_items),
                },
                "status": "received",
                "createdAt": current_timestamp(),
            }

            for item in order_items:
                product = find_product(products, item["productId"])
                product["stock"] = int(product["stock"]) - item["quantity"]

            store["orders"].append(order)
            cart["items"] = []
            cart["updatedAt"] = current_timestamp()
            save_products(products)
            save_store(store)

        self.send_json(HTTPStatus.CREATED, {
            "order": order,
            "sessionId": cart["sessionId"],
            "cart": build_cart_response(cart, products),
        })

    def handle_get_order(self, order_id):
        with DATA_LOCK:
            store = read_store()
            order = next((item for item in store["orders"] if item.get("id") == order_id), None)

        if not order:
            raise ApiError(HTTPStatus.NOT_FOUND, "Pedido não encontrado.")

        self.send_json(HTTPStatus.OK, {"order": order})

    def read_body(self):
        content_length = int(self.headers.get("Content-Length", 0))

        if content_length > MAX_BODY_SIZE:
            raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "O corpo da requisição é muito grande.")

        raw_body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"

        try:
            body = json.loads(raw_body or "{}")
        except json.JSONDecodeError:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Envie um JSON válido.")

        if not isinstance(body, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Envie um objeto JSON válido.")

        return body

    def serve_static(self, request_path):
        if self.command not in {"GET", "HEAD"}:
            raise ApiError(HTTPStatus.METHOD_NOT_ALLOWED, "Método não permitido.")

        safe_path = unquote(request_path or "/")
        if safe_path == "/":
            safe_path = "/index.html"

        requested_file = (PUBLIC_DIR / safe_path.lstrip("/")).resolve()

        try:
            requested_file.relative_to(PUBLIC_DIR.resolve())
        except ValueError:
            raise ApiError(HTTPStatus.FORBIDDEN, "Acesso negado.")

        if not requested_file.is_file():
            raise ApiError(HTTPStatus.NOT_FOUND, "Arquivo não encontrado.")

        content_type = mimetypes.guess_type(requested_file.name)[0] or "application/octet-stream"
        cache_control = "public, max-age=86400" if "/assets/" in safe_path else "no-store"
        content = requested_file.read_bytes()

        self.send_response(HTTPStatus.OK)
        self.send_header("Cache-Control", cache_control)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Content-Type", content_type)
        self.end_headers()

        if self.command != "HEAD":
            self.wfile.write(content)

    def send_json(self, status_code, payload):
        encoded_payload = b"" if status_code == HTTPStatus.NO_CONTENT else json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(encoded_payload)))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()

        if encoded_payload:
            self.wfile.write(encoded_payload)

    def log_message(self, format, *args):
        return


def main():
    ensure_data_files()
    server = ThreadingHTTPServer(("localhost", PORT), NocturnaHandler)
    print(f"Nocturna Atelier rodando em http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
