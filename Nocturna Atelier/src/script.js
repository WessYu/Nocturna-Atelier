"use strict";

const header = document.querySelector("[data-header]");
const revealItems = document.querySelectorAll(".reveal");
const cartCount = document.querySelector("[data-cart-count]");
const cartButtons = document.querySelectorAll("[data-add-cart]");
const toast = document.querySelector("[data-toast]");

let cartTotal = 0;
let toastTimer;

const setHeaderState = () => {
  if (!header) return;
  header.classList.toggle("scrolled", window.scrollY > 12);
};

const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (!entry.isIntersecting) return;
    entry.target.classList.add("visible");
    revealObserver.unobserve(entry.target);
  });
}, { threshold: 0.18 });

revealItems.forEach((item) => revealObserver.observe(item));

cartButtons.forEach((button) => {
  button.addEventListener("click", () => {
    cartTotal += 1;
    if (cartCount) cartCount.textContent = cartTotal;
    if (!toast) return;
    toast.classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("visible"), 2200);
  });
});

window.addEventListener("scroll", setHeaderState, { passive: true });
setHeaderState();
