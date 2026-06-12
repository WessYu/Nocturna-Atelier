"use strict";

const CART_SESSION_KEY = "nocturna.cartSessionId";

const header = document.querySelector("[data-header]");
const revealItems = document.querySelectorAll(".reveal");
const cartCount = document.querySelector("[data-cart-count]");
const cartButtons = document.querySelectorAll("[data-add-cart]");
const cartOpenButton = document.querySelector("[data-open-cart]");
const cartCloseButton = document.querySelector("[data-close-cart]");
const cartDrawer = document.querySelector("[data-cart-drawer]");
const cartOverlay = document.querySelector("[data-cart-overlay]");
const cartItems = document.querySelector("[data-cart-items]");
const cartEmpty = document.querySelector("[data-cart-empty]");
const cartSubtotal = document.querySelector("[data-cart-subtotal]");
const newsletterForm = document.querySelector("[data-newsletter-form]");
const checkoutForm = document.querySelector("[data-checkout-form]");
const toast = document.querySelector("[data-toast]");

const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

const productsById = new Map();
let cartSessionId = readStoredSession();
let currentCart = { items: [], totals: { totalQuantity: 0, subtotalCents: 0 } };
let toastTimer;
let offlineWarningShown = false;

const setHeaderState = () => {
  if (!header) return;
  header.classList.toggle("scrolled", window.scrollY > 12);
};

const formatPrice = (valueInCents) => currencyFormatter.format(valueInCents / 100);

function readStoredSession() {
  try {
    return window.localStorage.getItem(CART_SESSION_KEY);
  } catch {
    return null;
  }
}

function storeSession(sessionId) {
  if (!sessionId || sessionId === cartSessionId) return;
  cartSessionId = sessionId;

  try {
    window.localStorage.setItem(CART_SESSION_KEY, sessionId);
  } catch {
    // A sacola continua funcionando na sessão atual mesmo sem localStorage.
  }
}

function showToast(message, type = "success") {
  if (!toast) return;
  toast.textContent = message;
  toast.classList.toggle("error", type === "error");
  toast.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("visible"), 2600);
}

function showOfflineWarning() {
  if (offlineWarningShown) return;
  offlineWarningShown = true;
  showToast("Backend indisponível. Inicie com npm start para usar a loja completa.", "error");
}

async function apiRequest(endpoint, options = {}) {
  const headers = new Headers(options.headers || {});
  const requestOptions = { ...options, headers };

  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    requestOptions.body = JSON.stringify(options.body);
  }

  const response = await fetch(endpoint, requestOptions);
  const payload = response.status === 204 ? null : await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(payload?.message || "Não foi possível completar a solicitação.");
  }

  return payload;
}

function hydrateCart(payload) {
  if (!payload) return;
  storeSession(payload.sessionId);
  currentCart = payload.cart || currentCart;
  renderCart();
}

async function loadProducts() {
  try {
    const payload = await apiRequest("/api/products");
    payload.products.forEach((product) => productsById.set(product.id, product));
    syncProductCards(payload.products);
  } catch (error) {
    console.warn(error);
    showOfflineWarning();
  }
}

async function loadCart() {
  try {
    const query = cartSessionId ? `?sessionId=${encodeURIComponent(cartSessionId)}` : "";
    hydrateCart(await apiRequest(`/api/cart${query}`));
  } catch (error) {
    console.warn(error);
    showOfflineWarning();
  }
}

function syncProductCards(products) {
  products.forEach((product) => {
    const card = document.querySelector(`[data-product-id="${product.id}"]`);
    if (!card) return;

    const price = card.querySelector(".product-row strong");
    const button = card.querySelector("[data-add-cart]");
    const image = card.querySelector("img");

    if (price) price.textContent = formatPrice(product.priceCents);
    if (image) {
      image.src = product.image;
      image.alt = product.alt;
    }
    if (button) {
      button.disabled = product.stock <= 0;
      button.textContent = product.stock > 0 ? "Adicionar" : "Esgotado";
    }
  });
}

async function addToCart(button) {
  const productId = button.dataset.addCart || button.closest("[data-product-id]")?.dataset.productId;
  if (!productId) return;

  button.disabled = true;

  try {
    const payload = await apiRequest("/api/cart/items", {
      method: "POST",
      body: { sessionId: cartSessionId, productId, quantity: 1 },
    });
    hydrateCart(payload);
    const productName = productsById.get(productId)?.name || "Peça";
    showToast(`${productName} adicionada à sacola.`);
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function updateCartItem(productId, quantity) {
  try {
    const payload = await apiRequest(`/api/cart/items/${encodeURIComponent(productId)}`, {
      method: "PATCH",
      body: { sessionId: cartSessionId, quantity },
    });
    hydrateCart(payload);
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function removeCartItem(productId) {
  try {
    const payload = await apiRequest(`/api/cart/items/${encodeURIComponent(productId)}`, {
      method: "DELETE",
      body: { sessionId: cartSessionId },
    });
    hydrateCart(payload);
  } catch (error) {
    showToast(error.message, "error");
  }
}

function renderCart() {
  const totalQuantity = currentCart.totals?.totalQuantity || 0;
  const subtotalCents = currentCart.totals?.subtotalCents || 0;

  if (cartCount) cartCount.textContent = totalQuantity;
  if (cartSubtotal) cartSubtotal.textContent = formatPrice(subtotalCents);
  if (!cartItems || !cartEmpty) return;

  cartItems.replaceChildren();
  cartEmpty.hidden = totalQuantity > 0;

  currentCart.items.forEach((item) => {
    const product = item.product;
    const article = document.createElement("article");
    article.className = "cart-item";
    article.innerHTML = `
      <img src="${product.image}" alt="${product.alt}">
      <div class="cart-item-copy">
        <span>${product.category}</span>
        <strong>${product.name}</strong>
        <small>${formatPrice(product.priceCents)}</small>
      </div>
      <div class="cart-item-actions">
        <button type="button" data-cart-action="decrease" data-product-id="${product.id}" aria-label="Diminuir quantidade">-</button>
        <span>${item.quantity}</span>
        <button type="button" data-cart-action="increase" data-product-id="${product.id}" aria-label="Aumentar quantidade">+</button>
        <button type="button" data-cart-action="remove" data-product-id="${product.id}" aria-label="Remover peça">Remover</button>
      </div>
    `;
    cartItems.append(article);
  });
}

function openCart() {
  if (!cartDrawer || !cartOverlay) return;
  cartDrawer.classList.add("visible");
  cartDrawer.setAttribute("aria-hidden", "false");
  cartOverlay.hidden = false;
}

function closeCart() {
  if (!cartDrawer || !cartOverlay) return;
  cartDrawer.classList.remove("visible");
  cartDrawer.setAttribute("aria-hidden", "true");
  cartOverlay.hidden = true;
}

async function submitNewsletter(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const submitButton = form.querySelector("button");
  const formData = new FormData(form);

  submitButton.disabled = true;

  try {
    const payload = await apiRequest("/api/newsletter", {
      method: "POST",
      body: { email: formData.get("email") },
    });
    showToast(payload.message);
    form.reset();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    submitButton.disabled = false;
  }
}

async function submitCheckout(event) {
  event.preventDefault();

  if (!currentCart.totals?.totalQuantity) {
    showToast("Adicione uma peça antes de finalizar o pedido.", "error");
    return;
  }

  const form = event.currentTarget;
  const submitButton = form.querySelector("button");
  const formData = new FormData(form);

  submitButton.disabled = true;

  try {
    const payload = await apiRequest("/api/orders", {
      method: "POST",
      body: {
        sessionId: cartSessionId,
        customer: {
          name: formData.get("name"),
          email: formData.get("email"),
        },
      },
    });
    hydrateCart(payload);
    form.reset();
    closeCart();
    showToast(`Pedido ${payload.order.id} recebido com sucesso.`);
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    submitButton.disabled = false;
  }
}

if ("IntersectionObserver" in window) {
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("visible");
      revealObserver.unobserve(entry.target);
    });
  }, { threshold: 0.18 });

  revealItems.forEach((item) => revealObserver.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add("visible"));
}

cartButtons.forEach((button) => {
  button.addEventListener("click", () => addToCart(button));
});

cartItems?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-cart-action]");
  if (!button) return;

  const productId = button.dataset.productId;
  const item = currentCart.items.find((cartItem) => cartItem.product.id === productId);
  if (!item) return;

  if (button.dataset.cartAction === "increase") updateCartItem(productId, item.quantity + 1);
  if (button.dataset.cartAction === "decrease") updateCartItem(productId, item.quantity - 1);
  if (button.dataset.cartAction === "remove") removeCartItem(productId);
});

cartOpenButton?.addEventListener("click", openCart);
cartCloseButton?.addEventListener("click", closeCart);
cartOverlay?.addEventListener("click", closeCart);
newsletterForm?.addEventListener("submit", submitNewsletter);
checkoutForm?.addEventListener("submit", submitCheckout);
window.addEventListener("scroll", setHeaderState, { passive: true });
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeCart();
});

setHeaderState();
renderCart();
loadProducts();
loadCart();
