document.addEventListener("DOMContentLoaded", () => {
    const orderId = sessionStorage.getItem("orderId");
    const totalAmount = sessionStorage.getItem("totalAmount");

    if (!orderId || !totalAmount) {
        alert("Invalid payment session");
        window.location.href = "/store";
        return;
    }

    document.getElementById("order-id").textContent = orderId;
    document.getElementById("total-amount").textContent = totalAmount;
});

function confirmPayment() {
    // For now: mock payment success
    sessionStorage.setItem("paymentSuccess", "true");

    window.location.href = "/payment-success";
}
