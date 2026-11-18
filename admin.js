const LOW_STOCK_THRESHOLD = 5;

let products = [];
let toastTimer;

const adminShell = document.querySelector("#admin-shell");
const adminLoadMessage = document.querySelector("#admin-load-message");
const productFormPanel = document.querySelector("#product-form-panel");
const productForm = document.querySelector("#product-form");
const productList = document.querySelector("#admin-product-list");
const adminSearch = document.querySelector("#admin-search");
const tableEmpty = document.querySelector("#table-empty");
const productMessage = document.querySelector("#product-message");
const settingsMessage = document.querySelector("#settings-message");
const toast = document.querySelector("#admin-toast");
const orderList = document.querySelector("#admin-order-list");
const ordersEmpty = document.querySelector("#orders-empty");
const productPhotoInput = productForm.elements.photo;
const productPhotoPreview = document.querySelector("#photo-upload-preview");
const MAX_PRODUCT_PHOTO_SIZE = 1024 * 1024;
const ALLOWED_PRODUCT_PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];
let photoPreviewUrl;

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

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 2400);
}

async function showAdmin() {
  try {
    const [savedProducts, settings] = await Promise.all([
      StoreData.getProducts(),
      StoreData.getSettings()
    ]);
    products = savedProducts;
    adminShell.hidden = false;
    renderProducts();
    await renderOrders();
    document.querySelector("#settings-form").elements.whatsapp.value = settings.whatsapp;
  } catch (error) {
    adminLoadMessage.textContent = `Database tidak dapat dimuat: ${error.message}`;
  }
}

function refreshDashboard() {
  const totalUnits = products.reduce((sum, product) => sum + product.stock, 0);
  const lowStock = products.filter((product) => product.stock <= LOW_STOCK_THRESHOLD);
  const stockValue = products.reduce((sum, product) => sum + product.price * product.stock, 0);

  document.querySelector("#metric-products").textContent = products.length;
  document.querySelector("#metric-stock").textContent = new Intl.NumberFormat("id-ID").format(totalUnits);
  document.querySelector("#metric-low-stock").textContent = lowStock.length;
  document.querySelector("#metric-value").textContent = formatPrice(stockValue);

  const lowStockList = document.querySelector("#low-stock-list");
  lowStockList.innerHTML = lowStock.length
    ? `<div class="low-stock-rows">${lowStock.map((product) => `
        <div class="low-stock-row">
          <span class="table-product-icon" style="background:${product.color || "#e9eee3"}" aria-hidden="true">${product.photo ? `<img src="${escapeHtml(product.photo)}" alt="">` : escapeHtml(product.icon || "🛍️")}</span>
          <span class="low-stock-name"><strong>${escapeHtml(product.name)}</strong><small>${escapeHtml(product.category)} · ${escapeHtml(product.unit)}</small></span>
          <span class="stock-badge stock-low">${product.stock} tersisa</span>
        </div>
      `).join("")}</div>`
    : '<div class="low-stock-empty">Semua stok produk lebih dari 5 unit. Bagus!</div>';
}

function renderProducts() {
  const query = adminSearch.value.trim().toLocaleLowerCase("id-ID");
  const filtered = products.filter((product) =>
    `${product.name} ${product.category}`.toLocaleLowerCase("id-ID").includes(query)
  );

  productList.innerHTML = filtered.map((product) => `
    <tr>
      <td><span class="table-product">
        <span class="table-product-icon" style="background:${product.color || "#e9eee3"}" aria-hidden="true">${product.photo ? `<img src="${escapeHtml(product.photo)}" alt="">` : escapeHtml(product.icon || "🛍️")}</span>
        <span><strong>${escapeHtml(product.name)}</strong><small>${escapeHtml(product.unit)}</small></span>
      </span></td>
      <td><span class="category-label">${escapeHtml(product.category)}</span></td>
      <td class="price-cell">${formatPrice(product.price)}</td>
      <td><span class="stock-badge${product.stock <= LOW_STOCK_THRESHOLD ? " stock-low" : ""}">${product.stock} unit</span></td>
      <td><div class="row-actions">
        <button class="row-action" type="button" data-edit="${escapeHtml(product.id)}">Ubah</button>
        <button class="row-action row-delete" type="button" data-delete="${escapeHtml(product.id)}">Hapus</button>
      </div></td>
    </tr>
  `).join("");

  document.querySelector("#products-summary").textContent = `${products.length} produk terdaftar`;
  tableEmpty.hidden = filtered.length !== 0;
  refreshDashboard();
}

async function renderOrders() {
  const orders = await StoreData.getOrders();
  orderList.innerHTML = orders.map((order) => `
    <tr>
      <td>${new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(order.createdAt))}</td>
      <td>${order.items.map((item) => `${escapeHtml(item.name)} × ${item.quantity}`).join("<br>")}</td>
      <td class="price-cell">${formatPrice(order.total)}</td>
      <td><span class="stock-badge">${escapeHtml(order.status)}</span></td>
      <td><button class="row-action row-delete" type="button" data-order-delete="${escapeHtml(order.id)}">Hapus</button></td>
    </tr>
  `).join("");
  document.querySelector("#orders-summary").textContent = `${orders.length} pesanan tersimpan`;
  ordersEmpty.hidden = orders.length !== 0;
}

function openProductForm(product) {
  if (photoPreviewUrl) URL.revokeObjectURL(photoPreviewUrl);
  photoPreviewUrl = undefined;
  productForm.reset();
  productMessage.textContent = "";
  productForm.elements.id.value = product ? product.id : "";
  productForm.elements.name.value = product ? product.name : "";
  productForm.elements.category.value = product ? product.category : "";
  productForm.elements.price.value = product ? product.price : "";
  productForm.elements.unit.value = product ? product.unit : "";
  productForm.elements.stock.value = product ? product.stock : 0;
  productForm.elements.tag.value = product ? product.tag : "";
  productPhotoInput.value = "";
  productPhotoInput.required = !product;
  productPhotoPreview.hidden = !product || !product.photo;
  if (product && product.photo) productPhotoPreview.src = product.photo;
  else productPhotoPreview.removeAttribute("src");
  document.querySelector("#product-form-title").textContent = product ? "Ubah produk" : "Tambah produk";
  productFormPanel.hidden = false;
  productFormPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeProductForm() {
  if (photoPreviewUrl) URL.revokeObjectURL(photoPreviewUrl);
  photoPreviewUrl = undefined;
  productFormPanel.hidden = true;
  productForm.reset();
  productPhotoPreview.hidden = true;
  productPhotoPreview.removeAttribute("src");
}

function switchView(viewName) {
  document.querySelectorAll(".admin-view").forEach((view) => {
    view.hidden = view.id !== `view-${viewName}`;
  });
  document.querySelectorAll(".admin-nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewName);
  });
  if (viewName !== "products") closeProductForm();
}

function readProductPhoto(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => {
      if (typeof reader.result !== "string") {
        reject(new Error("Foto tidak dapat dibaca."));
        return;
      }
      resolve(reader.result);
    });
    reader.addEventListener("error", () => reject(new Error("Foto tidak dapat dibaca.")));
    reader.readAsDataURL(file);
  });
}

async function saveProduct(event) {
  event.preventDefault();
  const formData = new FormData(productForm);
  const existingId = String(formData.get("id"));
  const name = String(formData.get("name")).trim();
  const id = existingId || `${name.toLocaleLowerCase("id-ID").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}-${Date.now().toString(36)}`;
  const existingProduct = products.find((item) => item.id === existingId);
  const photoFile = productPhotoInput.files[0];
  if (photoFile && !ALLOWED_PRODUCT_PHOTO_TYPES.includes(photoFile.type)) {
    productMessage.textContent = "Format foto harus JPG, PNG, WebP, atau GIF.";
    return;
  }
  if (photoFile && (photoFile.size === 0 || photoFile.size > MAX_PRODUCT_PHOTO_SIZE)) {
    productMessage.textContent = "Ukuran foto harus lebih dari 0 dan maksimal 1 MB.";
    return;
  }

  let photo = existingProduct ? existingProduct.photo : "";
  if (photoFile) {
    try {
      photo = await readProductPhoto(photoFile);
    } catch (error) {
      productMessage.textContent = error.message;
      return;
    }
  }

  const product = {
    id,
    name,
    category: String(formData.get("category")).trim(),
    price: Number(formData.get("price")),
    unit: String(formData.get("unit")).trim(),
    stock: Number(formData.get("stock")),
    tag: String(formData.get("tag")).trim()
  };
  if (photo) product.photo = photo;
  if (existingProduct && existingProduct.icon) product.icon = existingProduct.icon;
  if (existingProduct && existingProduct.color) product.color = existingProduct.color;

  if (!Number.isSafeInteger(product.price) || product.price < 1 ||
      !Number.isSafeInteger(product.stock) || product.stock < 0 ||
      !product.name || !product.category || !product.unit || (!product.photo && !product.icon)) {
    productMessage.textContent = "Periksa kembali nama, kategori, harga, satuan, stok, dan foto produk.";
    return;
  }

  const nextProducts = existingId
    ? products.map((item) => item.id === existingId ? product : item)
    : [...products, product];

  if (!existingId && products.some((item) => item.id === id)) {
    productMessage.textContent = "Produk dengan ID tersebut sudah ada. Ubah nama produk dan coba lagi.";
    return;
  }

  try {
    await StoreData.saveProducts(nextProducts);
    products = nextProducts;
    renderProducts();
    closeProductForm();
    showToast(existingId ? "Produk berhasil diperbarui" : "Produk berhasil ditambahkan");
  } catch (error) {
    productMessage.textContent = `Produk tidak dapat disimpan: ${error.message}`;
  }
}

async function removeProduct(productId) {
  const product = products.find((item) => item.id === productId);
  if (!product || !window.confirm(`Hapus "${product.name}" dari katalog?`)) return;

  const nextProducts = products.filter((item) => item.id !== productId);
  try {
    await StoreData.saveProducts(nextProducts);
    products = nextProducts;
    renderProducts();
    showToast("Produk berhasil dihapus");
  } catch (error) {
    showToast(`Produk tidak dapat dihapus: ${error.message}`);
  }
}

document.querySelectorAll(".admin-nav-item").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

document.querySelectorAll("[data-open-view]").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.openView));
});

document.querySelector("#logout-button").addEventListener("click", async () => {
  try {
    await StoreData.logout();
  } catch (error) {
    showToast(`Tidak dapat keluar: ${error.message}`);
    return;
  }
  window.location.replace("login.html");
});

document.querySelector("#new-product-button").addEventListener("click", () => openProductForm());
document.querySelector("#cancel-product-button").addEventListener("click", closeProductForm);
document.querySelector("#cancel-product-action").addEventListener("click", closeProductForm);
productForm.addEventListener("submit", saveProduct);
productPhotoInput.addEventListener("change", () => {
  if (photoPreviewUrl) URL.revokeObjectURL(photoPreviewUrl);
  photoPreviewUrl = undefined;
  const file = productPhotoInput.files[0];
  if (!file) {
    productPhotoPreview.hidden = true;
    productPhotoPreview.removeAttribute("src");
    return;
  }
  if (!ALLOWED_PRODUCT_PHOTO_TYPES.includes(file.type) || file.size > MAX_PRODUCT_PHOTO_SIZE) return;
  photoPreviewUrl = URL.createObjectURL(file);
  productPhotoPreview.src = photoPreviewUrl;
  productPhotoPreview.hidden = false;
});
adminSearch.addEventListener("input", renderProducts);

productList.addEventListener("click", (event) => {
  const editButton = event.target.closest("[data-edit]");
  const deleteButton = event.target.closest("[data-delete]");
  if (editButton) openProductForm(products.find((product) => product.id === editButton.dataset.edit));
  if (deleteButton) removeProduct(deleteButton.dataset.delete);
});

orderList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-order-delete]");
  if (!button) return;
  try {
    const order = (await StoreData.getOrders()).find((item) => item.id === button.dataset.orderDelete);
    if (!order || !window.confirm("Hapus pesanan ini dari riwayat?")) return;
    await StoreData.deleteOrder(order.id);
    await renderOrders();
    showToast("Pesanan berhasil dihapus");
  } catch (error) {
    showToast(`Pesanan tidak dapat dihapus: ${error.message}`);
  }
});

document.querySelector("#settings-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = event.currentTarget.elements.whatsapp;
  const whatsapp = input.value.replace(/[\s()+-]/g, "");
  if (!/^\d{8,15}$/.test(whatsapp)) {
    settingsMessage.textContent = "Masukkan nomor 8–15 digit dengan kode negara, contoh 6281234567890.";
    return;
  }

  try {
    await StoreData.saveSettings({ whatsapp });
    input.value = whatsapp;
    settingsMessage.textContent = "Nomor WhatsApp berhasil disimpan.";
    showToast("Pengaturan toko berhasil disimpan");
  } catch (error) {
    settingsMessage.textContent = `Pengaturan tidak dapat disimpan: ${error.message}`;
  }
});

async function startDashboard() {
  try {
    await StoreData.initialize();
    const session = await StoreData.checkSession();
    if (!session.authenticated) {
      window.location.replace("login.html");
      return;
    }
    await showAdmin();
  } catch (error) {
    adminShell.hidden = false;
    adminLoadMessage.textContent = `Database tidak dapat diakses: ${error.message}. Jalankan python server.py terlebih dahulu.`;
  }
}

startDashboard();
