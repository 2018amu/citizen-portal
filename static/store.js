// -----------------------------
// Globals
// -----------------------------
let cart = JSON.parse(localStorage.getItem('cart')) || [];
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
        const res = await fetch('/api/store/categories');
        const data = await res.json();

        const container = document.getElementById('category-filters');
        if (!container) return;

        container.innerHTML = '';

        data.categories.forEach(category => {
            const label = document.createElement('label');
            label.innerHTML = `
                <input type="checkbox" name="category" value="${category}">
                ${category.charAt(0).toUpperCase() + category.slice(1)}
            `;
            container.appendChild(label);
        });
    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

// -----------------------------
// Load Products
// -----------------------------
async function loadProducts() {
    const loading = document.getElementById('loading');
    if (loading) loading.style.display = 'block';

    const params = new URLSearchParams();

    if (currentFilters.category) params.append('category', currentFilters.category);
    if (currentFilters.minPrice) params.append('min_price', currentFilters.minPrice);
    if (currentFilters.maxPrice) params.append('max_price', currentFilters.maxPrice);
    if (currentFilters.delivery) params.append('delivery', currentFilters.delivery.join(','));

    const sortBy = document.getElementById('sort-by')?.value || 'name';
    params.append('sort', sortBy);

    try {
        const res = await fetch(`/api/store/products?${params}`);
        currentProducts = await res.json();
        displayProducts(currentProducts);
    } catch (error) {
        console.error('Error loading products:', error);
    } finally {
        if (loading) loading.style.display = 'none';
    }
}

// -----------------------------
// Display Products
// -----------------------------
function displayProducts(products) {
    const container = document.getElementById('products-container');
    if (!container) return;

    if (!products || products.length === 0) {
        container.innerHTML = '<div class="no-products">No products found.</div>';
        return;
    }

    container.innerHTML = products.map(product => `
        <div class="product-card" onclick="openProductModal('${product.id}')">
            <div class="product-image">
                <img src="${product.images?.[0] || '/static/store/placeholder.jpg'}" 
                     alt="${product.name}"
                     onerror="this.src='/static/store/placeholder.jpg'">
            </div>

            <div class="product-info">
                <h3 class="product-name">${product.name}</h3>

                <div class="product-price">
                    ${product.original_price ? `<span class="original-price">LKR ${product.original_price.toLocaleString()}</span>` : ''}
                    <span class="current-price">LKR ${product.price.toLocaleString()}</span>
                </div>

                <button onclick="event.stopPropagation(); addToCart('${product.id}')">Add to Cart</button>
            </div>
        </div>
    `).join('');
}

// -----------------------------
// Cart Management
// -----------------------------
function addToCart(productId) {
    const product = currentProducts.find(p => p.id === productId);
    if (!product) return;

    const existingItem = cart.find(i => i.id === productId);
    if (existingItem) {
        existingItem.quantity++;
    } else {
        cart.push({
            id: product.id,
            name: product.name,
            price: product.price,
            image: product.images?.[0] || "/static/store/placeholder.jpg",
            quantity: 1
        });
    }

    updateCart();
    showNotification(`${product.name} added to cart!`);
}

function updateCart() {
    localStorage.setItem("cart", JSON.stringify(cart));
    updateCartCount();
    updateCartModal();
}

function updateCartCount() {
    const count = cart.reduce((sum, item) => sum + item.quantity, 0);
    const cartCount = document.getElementById('cart-count');
    if (cartCount) cartCount.textContent = count;
}

function viewCart() {
    document.getElementById('cart-modal').style.display = 'block';
    updateCartModal();
}

function closeCart() {
    document.getElementById('cart-modal').style.display = 'none';
}

function updateCartModal() {
    const container = document.getElementById('cart-items');
    const total = document.getElementById('cart-total');

    container.innerHTML = cart.length === 0
        ? "<p>Your cart is empty</p>"
        : cart.map(item => `
            <div class="cart-item">
                <img src="${item.image}">
                <div>
                    <h4>${item.name}</h4>
                    <p>LKR ${item.price.toLocaleString()}</p>
                </div>
                <div class="cart-controls">
                    <button onclick="updateQuantity('${item.id}', -1)">-</button>
                    <span>${item.quantity}</span>
                    <button onclick="updateQuantity('${item.id}', 1)">+</button>
                    <button onclick="removeFromCart('${item.id}')">Remove</button>
                </div>
            </div>
        `).join('');

    const totalValue = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
    total.textContent = totalValue.toLocaleString();
}

function updateQuantity(id, change) {
    const item = cart.find(i => i.id === id);
    if (!item) return;

    item.quantity += change;
    if (item.quantity <= 0) removeFromCart(id);
    updateCart();
}

function removeFromCart(id) {
    cart = cart.filter(i => i.id !== id);
    updateCart();
}

// -----------------------------
// Product Modal
// -----------------------------
function openProductModal(productId) {
    const product = currentProducts.find(p => p.id === productId);
    if (!product) return;

    const modal = document.getElementById("product-modal");
    const content = document.getElementById("modal-content");

    content.innerHTML = `
        <h2>${product.name}</h2>
        <img src="${product.images?.[0] || '/static/store/placeholder.jpg'}" class="main-image">

        <div class="thumbnails">
            ${product.images?.map(img => `<img src="${img}" onclick="changeMainImage('${img}')">`).join("")}
        </div>

        <p>LKR ${product.price.toLocaleString()}</p>
        <button onclick="addToCart('${product.id}')">Add To Cart</button>
    `;

    modal.style.display = "block";
}

function changeMainImage(src) {
    document.querySelector(".main-image").src = src;
}

function closeModal() {
    document.getElementById("product-modal").style.display = "none";
}

// -----------------------------
// Filters
// -----------------------------
function toggleFilters() {
    const sidebar = document.getElementById("filters-sidebar");
    sidebar.style.display = sidebar.style.display === "none" ? "block" : "none";
}

function applyFilters() {
    const categories = [...document.querySelectorAll('input[name="category"]:checked')].map(cb => cb.value);
    const delivery = [...document.querySelectorAll('input[name="delivery"]:checked')].map(cb => cb.value);

    currentFilters = {
        category: categories.join(","),
        delivery: delivery,
        minPrice: 0,
        maxPrice: parseInt(document.getElementById('price-range').value)
    };

    loadProducts();
}

function clearFilters() {
    document.querySelectorAll("input[type='checkbox']").forEach(cb => cb.checked = false);
    document.getElementById("price-range").value = 500000;
    updatePriceDisplay();

    currentFilters = {};
    loadProducts();
}

function updatePriceDisplay() {
    const range = document.getElementById("price-range");
    document.getElementById("min-price").textContent = "0";
    document.getElementById("max-price").textContent = parseInt(range.value).toLocaleString();
}

// -----------------------------
// Notification Popup
// -----------------------------
function showNotification(message) {
    const note = document.createElement("div");
    note.className = "notification";
    note.textContent = message;
    document.body.appendChild(note);

    setTimeout(() => note.remove(), 3000);
}

// -----------------------------
// Init
// -----------------------------
document.addEventListener("DOMContentLoaded", initStore);
