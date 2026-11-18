const loginForm = document.querySelector("#login-form");
const loginMessage = document.querySelector("#login-message");

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = loginForm.elements.username.value.trim();
  const password = loginForm.elements.password.value;

  try {
    await StoreData.login(username, password);
    window.location.replace("admin.html");
  } catch (error) {
    loginMessage.textContent = error.message;
  }
});

async function startLogin() {
  try {
    await StoreData.initialize();
    const session = await StoreData.checkSession();
    if (session.authenticated) window.location.replace("admin.html");
  } catch (error) {
    loginMessage.textContent = `Database tidak dapat diakses: ${error.message}. Jalankan python server.py terlebih dahulu.`;
  }
}

startLogin();
