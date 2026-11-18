(function () {
  const LEGACY_KEYS = [
    "sembako-nusa-products-v1",
    "sembako-nusa-settings-v1",
    "sembako-nusa-orders-v1",
    "sembako-nusa-accounts-v1"
  ];

  async function request(path, options) {
    const response = await fetch(path, {
      credentials: "same-origin",
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options && options.headers)
      }
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Permintaan gagal (${response.status}).`);
    return result;
  }

  async function initialize() {
    const legacy = {};
    for (const key of LEGACY_KEYS) {
      const saved = localStorage.getItem(key);
      if (saved === null) continue;
      try {
        const value = JSON.parse(saved);
        if (key === LEGACY_KEYS[0]) legacy.products = value;
        else if (key === LEGACY_KEYS[1]) legacy.settings = value;
        else if (key === LEGACY_KEYS[2]) legacy.orders = value;
        else legacy.accounts = value;
      } catch (error) {
        console.error(`Data lama ${key} tidak dapat dibaca dan tidak dimigrasikan.`, error);
      }
    }

    const result = await request("/api/legacy-import", {
      method: "POST",
      body: JSON.stringify(legacy)
    });
    if (result.imported) LEGACY_KEYS.forEach((key) => localStorage.removeItem(key));
  }

  function getProducts() {
    return request("/api/products");
  }

  function saveProducts(products) {
    return request("/api/products", {
      method: "PUT",
      body: JSON.stringify(products)
    });
  }

  function getSettings() {
    return request("/api/settings");
  }

  function saveSettings(settings) {
    return request("/api/settings", {
      method: "PUT",
      body: JSON.stringify(settings)
    });
  }

  function getOrders() {
    return request("/api/orders");
  }

  function saveOrder(order) {
    return request("/api/orders", {
      method: "POST",
      body: JSON.stringify(order)
    });
  }

  function deleteOrder(orderId) {
    return request(`/api/orders/${encodeURIComponent(orderId)}`, { method: "DELETE" });
  }

  function login(username, password) {
    return request("/api/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    });
  }

  function logout() {
    return request("/api/logout", { method: "POST", body: "{}" });
  }

  function checkSession() {
    return request("/api/session");
  }

  window.StoreData = {
    initialize,
    getProducts,
    saveProducts,
    getSettings,
    saveSettings,
    getOrders,
    saveOrder,
    deleteOrder,
    login,
    logout,
    checkSession
  };
}());
