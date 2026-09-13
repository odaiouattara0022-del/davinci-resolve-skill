/* MonBudget — cache hors ligne : l'app reste utilisable sans réseau. */
const CACHE = "monbudget-v1";

self.addEventListener("install", (evenement) => {
  evenement.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(["./"])).catch(() => {}).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (evenement) => {
  evenement.waitUntil(
    caches.keys()
      .then((cles) => Promise.all(cles.filter((c) => c !== CACHE).map((c) => caches.delete(c))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (evenement) => {
  const requete = evenement.request;
  if (requete.method !== "GET") return;

  evenement.respondWith(
    fetch(requete)
      .then((reponse) => {
        const copie = reponse.clone();
        caches.open(CACHE).then((cache) => cache.put(requete, copie)).catch(() => {});
        return reponse;
      })
      .catch(() =>
        caches.match(requete, { ignoreSearch: true })
          .then((trouve) => trouve || caches.match("./", { ignoreSearch: true }))
      )
  );
});
