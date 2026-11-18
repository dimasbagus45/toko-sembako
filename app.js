let products = [];

const cart = new Map();
let activeCategory = "Semua";
let searchQuery = "";
let toastTimeout;

const productGrid = document.querySelector("#product-grid");
const categoryList = document.querySelector("#category-list");
const searchInput = document.querySelector("#product-search");
const cartCount = document.querySelector("#cart-count");
const cartHeadingCount = document.querySelector("#cart-heading-count");
const cartContent = document.querySelector("#cart-content");
const cartSummary = document.querySelector("#cart-summary");
const cartTotal = document.querySelector("#cart-total");
const emptyState = document.querySelector("#empty-state");
const productTotal = document.querySelector("#product-total");
const toast = document.querySelector("#toast");

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;"
  })[character]);
}

function formatPrice(amount) {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0
  }).format(amount);
}

function renderCategories() {
  const categories = ["Semua", ...new Set(products.map((product) => product.category))];
  categoryList.innerHTML = categories.map((category) => `
    <button class="category-chip${activeCategory === category ? " selected" : ""}"
      type="button" aria-pressed="${activeCategory === category}" data-category="${category}">
      ${escapeHtml(category)}
    </button>
  `).join("");
}

function renderProducts() {
  const filteredProducts = products.filter((product) => {
    const matchesCategory = activeCategory === "Semua" || product.category === activeCategory;
    const matchesSearch = `${product.name} ${product.category} ${product.unit}`
      .toLocaleLowerCase("id-ID").includes(searchQuery);
    return matchesCategory && matchesSearch;
  });

  productGrid.innerHTML = filteredProducts.map((product) => `
    <article class="product-card">
      <div class="product-art${product.photo ? " has-photo" : ""}" style="background:${product.color || "#e9eee3"}">
        ${product.tag ? `<span class="product-tag">${escapeHtml(product.tag)}</span>` : ""}
        ${product.photo ? `<img class="product-photo" src="${escapeHtml(product.photo)}" alt="${escapeHtml(product.name)}">` : `<span class="product-icon" aria-hidden="true">${escapeHtml(product.icon || "🛍️")}</span>`}
      </div>
      <div class="product-info">
        <span class="product-category">${escapeHtml(product.category)}</span>
        <h3 class="product-name">${escapeHtml(product.name)}</h3>
        <p class="product-unit">${escapeHtml(product.unit)} · Stok ${product.stock}</p>
        <div class="product-bottom">
          <span class="product-price">${formatPrice(product.price)}</span>
          <button class="add-button" type="button" data-add="${escapeHtml(product.id)}"
            aria-label="Tambahkan ${escapeHtml(product.name)} ke keranjang" ${product.stock === 0 ? "disabled" : ""}>${product.stock === 0 ? "×" : "+"}</button>
        </div>
      </div>
    </article>
  `).join("");

  productTotal.textContent = `${filteredProducts.length} produk`;
  emptyState.hidden = filteredProducts.length !== 0;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(toastTimeout);
  toastTimeout = window.setTimeout(() => toast.classList.remove("visible"), 2200);
}

function addToCart(productId) {
  const product = products.find((item) => item.id === productId);
  if (!product || product.stock <= 0) return;
  const quantity = cart.get(productId) || 0;
  if (quantity >= product.stock) {
    showToast("Jumlah pesanan sudah mencapai stok tersedia");
    return;
  }
  cart.set(productId, quantity + 1);
  renderCart();
  showToast(`${product.name} ditambahkan ke keranjang`);
}

function changeQuantity(productId, change) {
  const product = products.find((item) => item.id === productId);
  const quantity = (cart.get(productId) || 0) + change;
  if (quantity <= 0) cart.delete(productId);
  else if (!product || quantity > product.stock) {
    showToast("Jumlah pesanan sudah mencapai stok tersedia");
    return;
  }
  else cart.set(productId, quantity);
  renderCart();
}

function renderCart() {
  const cartEntries = [...cart.entries()];
  const itemCount = cartEntries.reduce((total, [, quantity]) => total + quantity, 0);
  const subtotal = cartEntries.reduce((total, [id, quantity]) => {
    const product = products.find((item) => item.id === id);
    return total + product.price * quantity;
  }, 0);

  cartCount.textContent = itemCount;
  cartHeadingCount.textContent = `${itemCount} produk`;
  cartSummary.hidden = itemCount === 0;

  if (itemCount === 0) {
    cartContent.innerHTML = '<div class="cart-empty"><div><span aria-hidden="true">🧺</span>Keranjangmu masih kosong. Yuk, pilih kebutuhanmu!</div></div>';
    return;
  }

  cartContent.innerHTML = cartEntries.map(([id, quantity]) => {
    const product = products.find((item) => item.id === id);
    return `
      <div class="cart-item">
        <span class="cart-item-icon" style="background:${product.color || "#e9eee3"}" aria-hidden="true">${product.photo ? `<img src="${escapeHtml(product.photo)}" alt="">` : escapeHtml(product.icon || "🛍️")}</span>
        <span class="cart-item-info"><strong>${escapeHtml(product.name)}</strong><small>${formatPrice(product.price)} / ${escapeHtml(product.unit)}</small></span>
        <span class="cart-item-total">${formatPrice(product.price * quantity)}</span>
        <span class="quantity-control">
          <button class="quantity-button" type="button" data-change="-1" data-id="${escapeHtml(id)}" aria-label="Kurangi ${escapeHtml(product.name)}">−</button>
          <span class="quantity-value">${quantity}</span>
          <button class="quantity-button" type="button" data-change="1" data-id="${escapeHtml(id)}" aria-label="Tambah ${escapeHtml(product.name)}" ${quantity >= product.stock ? "disabled" : ""}>+</button>
        </span>
      </div>
    `;
  }).join("");

  cartTotal.textContent = formatPrice(subtotal);
}

async function checkout() {
  if (cart.size === 0) {
    showToast("Keranjangmu masih kosong");
    return;
  }

  const lines = [...cart.entries()].map(([id, quantity]) => {
    const product = products.find((item) => item.id === id);
    return `- ${product.name} (${product.unit}) x${quantity} = ${formatPrice(product.price * quantity)}`;
  });
  const subtotal = [...cart.entries()].reduce((total, [id, quantity]) => {
    return total + products.find((product) => product.id === id).price * quantity;
  }, 0);
  const checkoutWindow = window.open("about:blank", "_blank");
  if (checkoutWindow) checkoutWindow.opener = null;
  let settings;
  const order = {
    id: `ORD-${Date.now().toString(36).toUpperCase()}-${Math.random().toString(36).slice(2, 7).toUpperCase()}`,
    createdAt: new Date().toISOString(),
    status: "Menunggu konfirmasi",
    whatsapp: "",
    total: subtotal,
    items: [...cart.entries()].map(([id, quantity]) => {
      const product = products.find((item) => item.id === id);
      return {
        id: product.id,
        name: product.name,
        unit: product.unit,
        price: product.price,
        quantity
      };
    })
  };
  try {
    settings = await StoreData.getSettings();
    order.whatsapp = settings.whatsapp;
    await StoreData.saveOrder(order);
  } catch (error) {
    if (checkoutWindow) checkoutWindow.close();
    showToast(`Pesanan tidak dapat disimpan: ${error.message}`);
    return;
  }

  const message = [
    "Halo Sembako Nusa, saya ingin memesan:",
    "",
    ...lines,
    "",
    `Perkiraan total: ${formatPrice(subtotal)}`,
    "",
    "Mohon konfirmasi ketersediaan dan detail pesanannya. Terima kasih!"
  ].join("\n");

  if (checkoutWindow) {
    checkoutWindow.location.href = `https://wa.me/${settings.whatsapp}?text=${encodeURIComponent(message)}`;
    showToast("Pesanan tersimpan, lanjutkan konfirmasi melalui WhatsApp");
  } else {
    showToast("Pesanan tersimpan, tetapi pop-up diblokir. Izinkan pop-up untuk membuka WhatsApp.");
  }
}

categoryList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-category]");
  if (!button) return;
  activeCategory = button.dataset.category;
  renderCategories();
  renderProducts();
});

productGrid.addEventListener("click", (event) => {
  const button = event.target.closest("[data-add]");
  if (button) addToCart(button.dataset.add);
});

cartContent.addEventListener("click", (event) => {
  const button = event.target.closest("[data-change]");
  if (button) changeQuantity(button.dataset.id, Number(button.dataset.change));
});

searchInput.addEventListener("input", () => {
  searchQuery = searchInput.value.trim().toLocaleLowerCase("id-ID");
  renderProducts();
});

document.querySelector("#checkout-button").addEventListener("click", checkout);
document.querySelector("#current-year").textContent = new Date().getFullYear();

async function initializeStore() {
  try {
    await StoreData.initialize();
    products = await StoreData.getProducts();
    renderCategories();
    renderProducts();
    renderCart();
  } catch (error) {
    productTotal.textContent = "";
    emptyState.textContent = `Katalog tidak dapat dimuat: ${error.message}. Jalankan python server.py untuk membuka toko.`;
    emptyState.hidden = false;
  }
}

initializeStore();
