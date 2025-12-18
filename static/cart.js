let cart = JSON.parse(localStorage.getItem("cart")) || [];

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
async function checkout() {
    if (!cart.length) {
        alert("Your cart is empty");
        return;
    }

    // 1️⃣ Prepare order payload
    const orderData = {
        items: cart.map(item => ({
            product_id: item._id,
            name: item.name,
            price: item.price,
            quantity: item.quantity
        })),
        total_amount: cart.reduce(
            (sum, i) => sum + i.price * i.quantity, 0
        ),
        payment_method: "cod"
    };

    try {
        // 2️⃣ SEND order to backend HERE ⬇⬇⬇
        const response = await fetch("/api/store/order", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(orderData)
        });

        const data = await response.json();

        // 3️⃣ Handle backend response
        if (!response.ok) {
            alert(data.error || "Order failed");
            return;
        }

        // 4️⃣ Success → clear cart
        localStorage.removeItem("cart");
        cart = [];

        alert("Order placed successfully 🎉\nOrder ID: " + data.order_id);

        // 5️⃣ Redirect
        window.location.href = "/store";

    } catch (err) {
        console.error("Checkout error:", err);
        alert("Server error. Please try again.");
    }
}


document.addEventListener("DOMContentLoaded", renderCart);
