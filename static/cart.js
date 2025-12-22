// -----------------------------
// Load cart from localStorage
// -----------------------------
let cart = JSON.parse(localStorage.getItem("cart")) || [];

// -----------------------------
// Render Cart
// -----------------------------
function renderCart() {
    const container = document.getElementById("cart-items");
    const totalEl = document.getElementById("cart-total");

    if (!cart.length) {
        container.innerHTML = `
            <div class="empty">
                <h3>Your cart is empty 😕</h3>
                <p>Start shopping and add items to your cart.</p>
            </div>
        `;
        totalEl.textContent = "0";
        return;
    }

    let total = 0;

    container.innerHTML = cart.map((item, index) => {
        total += item.price * item.quantity;
        return `
        <div class="cart-item">
            <img src="${item.image}">
            <div class="cart-info">
                <h4>${item.name}</h4>
                <p>LKR ${item.price.toLocaleString()}</p>
            </div>
            <div class="qty-box">
                <button onclick="changeQty(${index}, -1)">−</button>
                <div class="qty">${item.quantity}</div>
                <button onclick="changeQty(${index}, 1)">+</button>
                <button class="remove" onclick="removeItem(${index})">✕</button>
            </div>
        </div>
        `;
    }).join("");

    totalEl.textContent = total.toLocaleString();
}

// -----------------------------
// Cart operations
// -----------------------------
function changeQty(index, change) {
    cart[index].quantity += change;
    if (cart[index].quantity <= 0) cart.splice(index, 1);
    saveCart();
}

function removeItem(index) {
    cart.splice(index, 1);
    saveCart();
}

function clearCart() {
    cart = [];
    saveCart();
}

function saveCart() {
    localStorage.setItem("cart", JSON.stringify(cart));
    renderCart();
}

function goBack() {
    window.location.href = "/store";
}

// -----------------------------
// Checkout
// -----------------------------
async function checkout() {
    if (!cart || cart.length === 0) {
        alert("Your cart is empty");
        return;
    }

    const orderData = {
        items: cart.map(item => ({
            product_id: item._id,
            name: item.name,
            price: item.price,
            quantity: item.quantity
        })),
        total_amount: cart.reduce((sum, i) => sum + i.price * i.quantity, 0),
        payment_method: "cod"
    };

    try {
        const response = await fetch("/api/store/order", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(orderData)
        });

        const data = await response.json();

<<<<<<< HEAD
        if (!response.ok) {
=======
        if (!response.ok || !data.success) {
>>>>>>> 92fba87385a28c3abb77ce1bc77e56c14399879e
            alert(data.error || "Order failed");
            return;
        }

<<<<<<< HEAD
        // ✅ Save success info
        sessionStorage.setItem("orderSuccess", "true");
        sessionStorage.setItem("orderId", data.order_id);

        // Clear cart
        localStorage.removeItem("cart");
=======
        // Clear cart locally
>>>>>>> 92fba87385a28c3abb77ce1bc77e56c14399879e
        cart = [];
        localStorage.removeItem("cart");

<<<<<<< HEAD
        // Redirect to store
        window.location.href = "/store";
=======
        // ✅ Show Order Submitted page
        const container = document.getElementById("cart-container"); // wrap cart page content in div#cart-container
        container.innerHTML = `
            <div class="order-submitted">
                <h2>Order Submitted Successfully 🎉</h2>
                <p>Order ID: ${data.order_id}</p>
                <button id="goPaymentBtn">Go to Payment</button>
            </div>
        `;

        // Add click listener to redirect to payment page
        document.getElementById("goPaymentBtn").addEventListener("click", () => {
            window.location.href = "/store/cart/payment";
        });
>>>>>>> 92fba87385a28c3abb77ce1bc77e56c14399879e

    } catch (error) {
        console.error("Checkout error:", error);
        alert("Server error. Please try again.");
    }
}


<<<<<<< HEAD



document.addEventListener("DOMContentLoaded", renderCart);
=======
// -----------------------------
// Initialize cart page
// -----------------------------
document.addEventListener("DOMContentLoaded", () => {
    renderCart();

    const btn = document.getElementById("checkoutBtn");
    if (btn) {
        btn.addEventListener("click", e => {
            e.preventDefault();
            checkout();
        });
    }
});
>>>>>>> 92fba87385a28c3abb77ce1bc77e56c14399879e
