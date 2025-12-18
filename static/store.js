// -----------------------------
// Globals
// -----------------------------
let cart = JSON.parse(localStorage.getItem("cart")) || [];
let currentProducts = [];
let currentFilters = {};
let profile_id = null;

// -----------------------------
// Initialize Store
// -----------------------------
async function initStore() {
    await loadCategories();
    await loadProducts();
    updateCartCount();
}

// -----------------------------
// Load Categories
// -----------------------------
async function loadCategories() {
    try {
        const res = await fetch("/api/store/categories");
        const data = await res.json();

        const container = document.getElementById("category-filters");
        if (!container) return;

        container.innerHTML = "";

        data.categories.forEach(category => {
            const label = document.createElement("label");
            label.innerHTML = `
                <input type="checkbox" name="category" value="${category}">
                ${category.charAt(0).toUpperCase() + category.slice(1)}
            `;
            container.appendChild(label);
        });
    } catch (error) {
        console.error("Error loading categories:", error);
    }
}

// -----------------------------
// Toggle Filters Sidebar
// -----------------------------
function toggleFilters() {
    const sidebar = document.getElementById("filters-sidebar");
    if (!sidebar) return;

    sidebar.style.display =
        sidebar.style.display === "none" || sidebar.style.display === ""
            ? "block"
            : "none";
}

// -----------------------------
// Apply Filters
// -----------------------------
function applyFilters() {
    const categories = [...document.querySelectorAll('input[name="category"]:checked')]
        .map(cb => cb.value.toLowerCase());

    const delivery = [...document.querySelectorAll('input[name="delivery"]:checked')]
        .map(cb => cb.value.toLowerCase());

    const priceRange = document.getElementById("price-range");
    const maxPrice = priceRange ? parseInt(priceRange.value) : 500000;

    currentFilters = {
        category: categories.length ? categories.join(",") : null,
        delivery: delivery.length ? delivery.join(",") : null,
        minPrice: 0,
        maxPrice: maxPrice
    };

    console.log("applyFilters ->", currentFilters);
    loadProducts();
}

// -----------------------------
// Load Products
// -----------------------------
async function loadProducts() {
    const loading = document.getElementById("loading");
    if (loading) loading.style.display = "block";

    try {
        const params = new URLSearchParams();

        if (currentFilters.category)
            params.append("category", currentFilters.category);

        if (currentFilters.delivery)
            params.append("delivery", currentFilters.delivery);

        if (typeof currentFilters.minPrice === "number")
            params.append("min_price", currentFilters.minPrice);

        if (typeof currentFilters.maxPrice === "number")
            params.append("max_price", currentFilters.maxPrice);

        const sortBy = document.getElementById("sort-by")?.value || "name";
        params.append("sort", sortBy);

        const url = `/api/store/products?${params.toString()}`;
        console.log("loadProducts ->", url);

        const res = await fetch(url);
        const data = await res.json();

        currentProducts = Array.isArray(data)
            ? data
            : Array.isArray(data.products)
            ? data.products
            : [];

        displayProducts(currentProducts);

    } catch (error) {
        console.error("Error loading products:", error);
    } finally {
        if (loading) loading.style.display = "none";
    }
}
// Global cart function
function viewCart() {
  console.log("Cart clicked");
  window.location.href = "/store/cart";
}
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("cartBtn")
      ?.addEventListener("click", viewCart);
});



// -----------------------------
// Display Products
// -----------------------------
function displayProducts(products) {
    const container = document.getElementById("products-container");
    if (!container) return;

    if (!products.length) {
        container.innerHTML = `<div class="no-products">No products found</div>`;
        return;
    }

    container.innerHTML = products.map(product => `
        <div class="product-card" onclick="openProductModal('${product._id}')">
            <div class="product-image">
                <img src="${product.images?.[0] || "/static/store/placeholder.jpg"}"
                     onerror="this.src='/static/store/placeholder.jpg'">
            </div>
            <div class="product-info">
                <h3>${product.name}</h3>
                <div class="product-price">
                    ${product.original_price
                        ? `<span class="original-price">LKR ${product.original_price.toLocaleString()}</span>`
                        : ""}
                    <span class="current-price">LKR ${product.price.toLocaleString()}</span>
                </div>
                <button onclick="event.stopPropagation(); addToCart('${product._id}')">
                    Add to Cart
                </button>
            </div>
        </div>
    `).join("");
}

// -----------------------------
// Cart Management
// -----------------------------
function addToCart(productId) {
    const product = currentProducts.find(p => p._id === productId);
    if (!product) return;

    const existing = cart.find(i => i._id === productId);
    if (existing) {
        existing.quantity++;
    } else {
        cart.push({
            _id: product._id,
            name: product.name,
            price: product.price,
            image: product.images?.[0] || "/static/store/placeholder.jpg",
            quantity: 1
        });
    }

    updateCart();
    showNotification(`${product.name} added to cart`);
    localStorage.setItem("cart", JSON.stringify(cart));
    alert("Added to cart");
}
// function addToCart(productId) {
//   const product = currentProducts.find(p => p._id === productId);
//   if (!product) return;

//   let cart = JSON.parse(localStorage.getItem("cart")) || [];

//   const existing = cart.find(i => i._id === productId);

//   if (existing) {
//       existing.quantity += 1;
//   } else {
//       cart.push({
//           _id: product._id,
//           name: product.name,
//           price: product.price,
//           image: product.images?.[0] || "/static/store/placeholder.jpg",
//           quantity: 1
//       });
//   }

//   localStorage.setItem("cart", JSON.stringify(cart));
//   alert("Added to cart");
//   updateCart();
  
// }


function updateCart() {
    localStorage.setItem("cart", JSON.stringify(cart));
    updateCartCount();
    updateCartModal();
}

function updateCartCount() {
    const count = cart.reduce((sum, i) => sum + i.quantity, 0);
    const el = document.getElementById("cart-count");
    if (el) el.textContent = count;
}

// -----------------------------
// Cart Modal
// -----------------------------
function updateCartModal() {
    const container = document.getElementById("cart-items");
    const total = document.getElementById("cart-total");

    if (!container || !total) return;

    container.innerHTML = cart.length
        ? cart.map(item => `
            <div class="cart-item">
                <img src="${item.image}">
                <div>
                    <h4>${item.name}</h4>
                    <p>LKR ${item.price.toLocaleString()}</p>
                </div>
                <div class="cart-controls">
                    <button onclick="updateQuantity('${item._id}', -1)">-</button>
                    <span>${item.quantity}</span>
                    <button onclick="updateQuantity('${item._id}', 1)">+</button>
                    <button onclick="removeFromCart('${item._id}')">Remove</button>
                </div>
            </div>
        `).join("")
        : "<p>Your cart is empty</p>";

    total.textContent = cart
        .reduce((sum, i) => sum + i.price * i.quantity, 0)
        .toLocaleString();
}

function updateQuantity(id, change) {
    const item = cart.find(i => i._id === id);
    if (!item) return;

    item.quantity += change;
    if (item.quantity <= 0) removeFromCart(id);
    updateCart();
}

function removeFromCart(id) {
    cart = cart.filter(i => i._id !== id);
    updateCart();
}

// -----------------------------
// Product Modal
// -----------------------------
function openProductModal(productId) {
    const product = currentProducts.find(p => p._id === productId);
    if (!product) return;

    const modal = document.getElementById("product-modal");
    const content = document.getElementById("modal-content");

    content.innerHTML = `
        <h2>${product.name}</h2>
        <img src="${product.images?.[0]}" class="main-image">
        <p>LKR ${product.price.toLocaleString()}</p>
        <button onclick="addToCart('${product._id}')">Add to Cart</button>
    `;

    modal.style.display = "block";
}

function closeModal() {
    document.getElementById("product-modal").style.display = "none";
}

// -----------------------------
// Clear Filters
// -----------------------------
function clearFilters() {
    document.querySelectorAll("input[type='checkbox']").forEach(cb => cb.checked = false);
    document.getElementById("price-range").value = 500000;

    currentFilters = {};
    loadProducts();
}

// -----------------------------
// Notifications
// -----------------------------
function showNotification(msg) {
    const n = document.createElement("div");
    n.className = "notification";
    n.textContent = msg;
    document.body.appendChild(n);
    setTimeout(() => n.remove(), 3000);
}

// -----------------------------
// Init
// -----------------------------
document.addEventListener("DOMContentLoaded", initStore);
