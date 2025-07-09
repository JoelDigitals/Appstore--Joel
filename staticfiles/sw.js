self.addEventListener("push", function(event) {
  const data = event.data.json();
  const title = data.title || "Neue Nachricht";
  const options = {
    body: data.body,
    icon: data.icon || "/static/img/icon.png",
    badge: data.badge || "/static/img/badge.png"
  };
  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});
