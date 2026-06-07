"use strict";

const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  tg.setHeaderColor("#080808");
  tg.setBackgroundColor("#080808");
}

const params = new URLSearchParams(location.search);
const API_BASE = (params.get("api") || window.TELEGA_HUB_API_BASE || "http://localhost:5080").replace(/\/$/, "");
const DEV_USER_ID = params.get("dev_user_id") || localStorage.getItem("tghub_dev_user_id") || "1001";
localStorage.setItem("tghub_dev_user_id", DEV_USER_ID);

const state = {
  me: null,
  feed: null,
  view: "feed",
  activeSlug: null,
};

const $screen = document.getElementById("screen");
const $toast = document.getElementById("toast");
const $balance = document.getElementById("balanceStars");
const $adminTab = document.getElementById("adminTab");

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function headers(extra = {}) {
  const base = { ...extra };
  if (tg?.initData) {
    base["X-Telegram-Init-Data"] = tg.initData;
  } else {
    base["X-Debug-User-Id"] = DEV_USER_ID;
  }
  return base;
}

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: headers(options.headers || {}),
  });
  const type = res.headers.get("content-type") || "";
  const data = type.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    throw new Error(data?.detail || data || `HTTP ${res.status}`);
  }
  return data;
}

async function apiForm(path, form, method = "POST") {
  return api(path, { method, body: form });
}

function toast(message) {
  $toast.textContent = message;
  $toast.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => $toast.classList.add("hidden"), 3200);
}

function money(stars) {
  return `${stars} Stars`;
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.view === view);
  });
  render();
}

async function bootstrap() {
  try {
    state.me = await api("/api/me");
    $balance.textContent = state.me.balance_stars || 0;
    $adminTab.classList.toggle("hidden", !state.me.is_admin);
    state.feed = await api("/api/feed");
    render();
  } catch (error) {
    $screen.innerHTML = `<div class="empty">${esc(error.message)}</div>`;
  }
}

function render() {
  if (!state.me) return;
  $balance.textContent = state.me.balance_stars || 0;
  if (!state.me.age_confirmed) {
    renderAgeGate();
    return;
  }
  if (state.view === "creator") renderCreator();
  else if (state.view === "balance") renderBalance();
  else if (state.view === "admin") renderAdmin();
  else renderFeed();
}

function renderAgeGate() {
  $screen.innerHTML = `
    <section class="band">
      <h1>Telega HUB</h1>
      <div class="form">
        <h2>Подтверждение возраста</h2>
        <p class="muted">Доступ к материалам и публикации разрешены только совершеннолетним пользователям.</p>
        <button class="btn primary" type="button" data-action="age-confirm">Мне есть 18 лет</button>
      </div>
    </section>
  `;
}

function creatorTile(creator) {
  return `
    <article class="card creator-card">
      <div class="avatar" data-media="${esc(creator.avatar_url || "")}"></div>
      <div>
        <h3>${esc(creator.display_name)}</h3>
        <p class="muted">${esc(creator.posts_count)} постов</p>
      </div>
      <div class="price-line">
        <span>${money(creator.subscription_stars)} / мес</span>
        <span>${esc(creator.subscription_usd)}$</span>
      </div>
      <button class="btn primary" type="button" data-action="open-profile" data-slug="${esc(creator.slug)}">Профиль</button>
    </article>
  `;
}

function postTile(post) {
  const lockText = post.access_type === "paid" ? `Открыть за ${post.price_stars} Stars` : "По подписке";
  return `
    <article class="card post-card">
      <div class="post-media" data-media="${esc(post.media_url || post.teaser_url || "")}"></div>
      <div>
        <h3>${esc(post.title)}</h3>
        <p class="muted">${esc(post.caption)}</p>
      </div>
      <div class="price-line">
        <span>${post.locked ? "Закрыто" : "Открыто"}</span>
        <span>${post.access_type === "paid" ? money(post.price_stars) : "подписка"}</span>
      </div>
      ${
        post.locked && post.access_type === "paid"
          ? `<button class="btn primary" type="button" data-action="buy-post" data-id="${post.id}">${lockText}</button>`
          : ""
      }
    </article>
  `;
}

function renderFeed() {
  const feed = state.feed || { creators: [], posts: [] };
  $screen.innerHTML = `
    <section class="band">
      <div class="section-head">
        <div>
          <h1>Лента</h1>
          <p class="muted">Топ моделей и свежие посты</p>
        </div>
      </div>
      <div class="creator-grid">
        ${feed.creators.length ? feed.creators.map(creatorTile).join("") : `<div class="empty">Пока нет одобренных моделей</div>`}
      </div>
    </section>
    <section class="band">
      <h2>Свежие посты</h2>
      <div class="grid">
        ${feed.posts.length ? feed.posts.map(postTile).join("") : `<div class="empty">Постов пока нет</div>`}
      </div>
    </section>
  `;
  hydrateMedia();
}

async function renderProfile(slug) {
  try {
    const data = await api(`/api/creators/${encodeURIComponent(slug)}`);
    state.activeSlug = slug;
    const c = data.creator;
    $screen.innerHTML = `
      <section class="band">
        <button class="btn ghost" type="button" data-action="back-feed">Назад</button>
        <div class="card creator-card">
          <div class="avatar" data-media="${esc(c.avatar_url || "")}"></div>
          <div>
            <h1>${esc(c.display_name)}</h1>
            <p class="muted">${esc(c.bio)}</p>
          </div>
          <div class="price-line">
            <span>${money(c.subscription_stars)} / месяц</span>
            <span>${c.subscribed ? "Подписка активна" : "Нет подписки"}</span>
          </div>
          <div class="btn-row">
            ${
              c.subscribed
                ? `<button class="btn" type="button" disabled>Подписан</button>`
                : `<button class="btn primary" type="button" data-action="subscribe" data-id="${c.id}">Подписаться</button>`
            }
            <button class="btn" type="button" data-action="show-order" data-id="${c.id}">Эксклюзивное видео</button>
          </div>
        </div>
        <form class="form hidden" id="orderForm">
          <h2>Новый заказ</h2>
          <input type="hidden" name="creator_id" value="${c.id}" />
          <label class="field"><span>Задание</span><textarea name="description" required minlength="5"></textarea></label>
          <label class="field"><span>Сумма в Stars</span><input name="amount_stars" type="number" min="100" value="250" required /></label>
          <button class="btn primary" type="submit">Отправить заказ</button>
        </form>
      </section>
      <section class="band">
        <h2>Стена</h2>
        <div class="grid">${data.posts.length ? data.posts.map(postTile).join("") : `<div class="empty">Пока пусто</div>`}</div>
      </section>
    `;
    hydrateMedia();
    document.getElementById("orderForm")?.addEventListener("submit", submitOrder);
  } catch (error) {
    toast(error.message);
  }
}

function renderBalance() {
  const packs = [100, 250, 500, 1000];
  $screen.innerHTML = `
    <section class="band">
      <h1>Баланс</h1>
      <div class="stats">
        <div class="card stat-card"><span class="muted">Stars</span><strong>${state.me.balance_stars}</strong></div>
        <div class="card stat-card"><span class="muted">USD</span><strong>${state.me.balance_usd}$</strong></div>
        <div class="card stat-card"><span class="muted">Комиссия</span><strong>15%</strong></div>
      </div>
      <div class="grid">
        ${packs
          .map(
            (amount) => `
              <button class="card stat-card btn" type="button" data-action="topup" data-amount="${amount}">
                <span class="muted">Пополнить</span><strong>${amount}</strong>
              </button>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function creatorApplyForm() {
  return `
    <section class="band">
      <h1>Кабинет автора</h1>
      <form class="form" id="applyForm">
        <h2>Анкета модели</h2>
        <label class="field"><span>Имя</span><input name="display_name" required minlength="2" maxlength="96" /></label>
        <label class="field"><span>Описание</span><textarea name="bio" maxlength="1000"></textarea></label>
        <label class="field"><span>Цена подписки, Stars</span><input name="subscription_stars" type="number" min="1" value="250" required /></label>
        <label class="field"><span>Фото профиля без лица</span><input name="avatar" type="file" accept="image/*" /></label>
        <label class="field"><span>Пробное видео до 5 секунд</span><input name="trial_video" type="file" accept="video/*" /></label>
        <label class="field"><span>Лицо скрыто</span><select name="face_hidden"><option value="true">Да</option><option value="false">Нет</option></select></label>
        <button class="btn primary" type="submit">Отправить на проверку</button>
      </form>
    </section>
  `;
}

async function renderCreator() {
  const creator = state.me.creator;
  if (!creator) {
    $screen.innerHTML = creatorApplyForm();
    document.getElementById("applyForm")?.addEventListener("submit", submitApply);
    return;
  }

  let dashboard = null;
  let orders = { orders: [] };
  try {
    dashboard = await api("/api/creator/dashboard");
    orders = await api("/api/creator/orders");
  } catch (error) {
    $screen.innerHTML = `
      <section class="band">
        <h1>Кабинет автора</h1>
        <div class="empty">Статус анкеты: ${esc(creator.status)}</div>
      </section>
    `;
    return;
  }

  $screen.innerHTML = `
    <section class="band">
      <div class="section-head">
        <div>
          <h1>Кабинет автора</h1>
          <p class="muted">${esc(dashboard.creator.display_name)}</p>
        </div>
        <span class="status ${esc(dashboard.creator.status)}">${esc(dashboard.creator.status)}</span>
      </div>
      <div class="stats">
        <div class="card stat-card"><span class="muted">К выводу</span><strong>${dashboard.balance_stars}</strong></div>
        <div class="card stat-card"><span class="muted">Подписчики</span><strong>${dashboard.active_subscribers}</strong></div>
        <div class="card stat-card"><span class="muted">Заказы</span><strong>${dashboard.pending_orders}</strong></div>
      </div>
      <form class="form" id="postForm">
        <h2>Создать пост</h2>
        <label class="field"><span>Название</span><input name="title" required maxlength="120" /></label>
        <label class="field"><span>Подпись</span><textarea name="caption" maxlength="2000"></textarea></label>
        <label class="field"><span>Доступ</span><select name="access_type"><option value="subscription">По подписке</option><option value="paid">Платный пост</option></select></label>
        <label class="field"><span>Цена платного поста</span><input name="price_stars" type="number" min="0" value="0" /></label>
        <label class="field"><span>Материал</span><input name="media" type="file" accept="image/*,video/*" required /></label>
        <label class="field"><span>Тизер</span><input name="teaser" type="file" accept="image/*,video/*" /></label>
        <button class="btn primary" type="submit">Опубликовать</button>
      </form>
      <form class="form" id="withdrawForm">
        <h2>Вывод</h2>
        <label class="field"><span>Сумма Stars</span><input name="amount_stars" type="number" min="1" max="${dashboard.balance_stars}" required /></label>
        <label class="field"><span>TON / USDT кошелек или Telegram</span><input name="wallet" required maxlength="160" /></label>
        <button class="btn" type="submit">Запросить вывод</button>
      </form>
    </section>
    <section class="band">
      <h2>Заказы</h2>
      <div class="band">
        ${
          orders.orders.length
            ? orders.orders.map(orderCard).join("")
            : `<div class="empty">Новых заказов нет</div>`
        }
      </div>
    </section>
  `;
  document.getElementById("postForm")?.addEventListener("submit", submitPost);
  document.getElementById("withdrawForm")?.addEventListener("submit", submitWithdraw);
}

function orderCard(order) {
  return `
    <article class="card order-card">
      <div class="section-head">
        <h3>Заказ #${order.id}</h3>
        <span class="status ${esc(order.status)}">${esc(order.status)}</span>
      </div>
      <p>${esc(order.description)}</p>
      <div class="price-line"><span>${money(order.amount_stars)}</span><span>${order.deadline_at ? esc(order.deadline_at) : ""}</span></div>
      <div class="btn-row">
        ${order.status === "pending" ? `<button class="btn primary" data-action="accept-order" data-id="${order.id}">Принять</button><button class="btn danger" data-action="reject-order" data-id="${order.id}">Отклонить</button>` : ""}
        ${order.status === "accepted" ? `<label class="btn"><input class="hidden" type="file" accept="video/*" data-action="deliver-order" data-id="${order.id}" />Загрузить видео</label>` : ""}
      </div>
    </article>
  `;
}

async function renderAdmin() {
  try {
    const [summary, creators, withdrawals] = await Promise.all([
      api("/api/admin/summary"),
      api("/api/admin/creators"),
      api("/api/admin/withdrawals"),
    ]);
    $screen.innerHTML = `
      <section class="band">
        <h1>Админ</h1>
        <div class="stats">
          <div class="card stat-card"><span class="muted">Users</span><strong>${summary.users}</strong></div>
          <div class="card stat-card"><span class="muted">Pending</span><strong>${summary.creators_pending}</strong></div>
          <div class="card stat-card"><span class="muted">Withdraw</span><strong>${summary.withdrawals_pending}</strong></div>
        </div>
      </section>
      <section class="band">
        <h2>Модели</h2>
        <div class="grid">
          ${creators.creators.map(adminCreatorCard).join("") || `<div class="empty">Нет анкет</div>`}
        </div>
      </section>
      <section class="band">
        <h2>Выводы</h2>
        <div class="band">
          ${
            withdrawals.withdrawals
              .map((item) => `<div class="card order-card"><h3>#${item.id}</h3><p>${esc(item.wallet)}</p><div>${item.amount_stars} Stars</div></div>`)
              .join("") || `<div class="empty">Нет заявок</div>`
          }
        </div>
      </section>
    `;
    hydrateMedia();
  } catch (error) {
    $screen.innerHTML = `<div class="empty">${esc(error.message)}</div>`;
  }
}

function adminCreatorCard(creator) {
  return `
    <article class="card creator-card">
      <div class="avatar" data-media="${esc(creator.avatar_url || "")}"></div>
      <h3>${esc(creator.display_name)}</h3>
      <span class="status ${esc(creator.status)}">${esc(creator.status)}</span>
      <div class="btn-row">
        <button class="btn primary" data-action="approve-creator" data-id="${creator.id}">Approve</button>
        <button class="btn danger" data-action="reject-creator" data-id="${creator.id}">Reject</button>
      </div>
    </article>
  `;
}

async function hydrateMedia() {
  const nodes = [...document.querySelectorAll("[data-media]")].filter((node) => node.dataset.media);
  await Promise.all(nodes.map(loadMedia));
}

async function loadMedia(node) {
  try {
    const res = await fetch(`${API_BASE}${node.dataset.media}`, { headers: headers() });
    if (!res.ok) throw new Error("media locked");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const isVideo = blob.type.startsWith("video/");
    node.innerHTML = isVideo
      ? `<video src="${url}" playsinline controls preload="metadata"></video>`
      : `<img src="${url}" alt="" loading="lazy" />`;
  } catch {
    node.innerHTML = `<div class="media-loader">Закрыто</div>`;
  }
}

async function refreshAll(message) {
  state.me = await api("/api/me");
  state.feed = await api("/api/feed");
  toast(message);
  render();
}

async function submitApply(event) {
  event.preventDefault();
  try {
    const trial = event.target.elements.trial_video?.files?.[0];
    if (trial) {
      await assertVideoDuration(trial, 5);
    }
    await apiForm("/api/creators/apply", new FormData(event.target));
    await refreshAll("Анкета отправлена");
  } catch (error) {
    toast(error.message);
  }
}

function assertVideoDuration(file, maxSeconds) {
  return new Promise((resolve, reject) => {
    const video = document.createElement("video");
    const url = URL.createObjectURL(file);
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      URL.revokeObjectURL(url);
      if (video.duration > maxSeconds + 0.25) {
        reject(new Error(`Пробное видео должно быть до ${maxSeconds} секунд`));
      } else {
        resolve();
      }
    };
    video.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Не удалось прочитать пробное видео"));
    };
    video.src = url;
  });
}

async function submitPost(event) {
  event.preventDefault();
  try {
    await apiForm("/api/posts", new FormData(event.target));
    event.target.reset();
    await refreshAll("Пост опубликован");
  } catch (error) {
    toast(error.message);
  }
}

async function submitWithdraw(event) {
  event.preventDefault();
  try {
    await apiForm("/api/creator/withdrawals", new FormData(event.target));
    event.target.reset();
    await refreshAll("Заявка создана");
  } catch (error) {
    toast(error.message);
  }
}

async function submitOrder(event) {
  event.preventDefault();
  try {
    await apiForm("/api/orders", new FormData(event.target));
    await refreshAll("Заказ отправлен");
    if (state.activeSlug) await renderProfile(state.activeSlug);
  } catch (error) {
    toast(error.message);
  }
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-view], [data-action]");
  if (!button) return;

  const view = button.dataset.view;
  if (view) {
    setView(view);
    return;
  }

  const action = button.dataset.action;
  try {
    if (action === "age-confirm") {
      await api("/api/me/age-confirm", { method: "POST" });
      await refreshAll("Готово");
    } else if (action === "open-profile") {
      await renderProfile(button.dataset.slug);
    } else if (action === "back-feed") {
      setView("feed");
    } else if (action === "subscribe") {
      await api(`/api/creators/${button.dataset.id}/subscribe`, { method: "POST" });
      await refreshAll("Подписка активна");
      if (state.activeSlug) await renderProfile(state.activeSlug);
    } else if (action === "buy-post") {
      await api(`/api/posts/${button.dataset.id}/buy`, { method: "POST" });
      await refreshAll("Пост открыт");
    } else if (action === "show-order") {
      document.getElementById("orderForm")?.classList.toggle("hidden");
    } else if (action === "topup") {
      const form = new FormData();
      form.set("amount_stars", button.dataset.amount);
      const invoice = await apiForm("/api/wallet/stars-invoice", form);
      if (tg?.openInvoice) {
        tg.openInvoice(invoice.invoice_link, async () => {
          await refreshAll("Проверяю баланс");
        });
      } else {
        window.open(invoice.invoice_link, "_blank", "noopener");
      }
    } else if (action === "accept-order") {
      await api(`/api/creator/orders/${button.dataset.id}/accept`, { method: "POST" });
      await refreshAll("Заказ принят");
    } else if (action === "reject-order") {
      await api(`/api/creator/orders/${button.dataset.id}/reject`, { method: "POST" });
      await refreshAll("Заказ отклонен");
    } else if (action === "approve-creator") {
      await api(`/api/admin/creators/${button.dataset.id}/approve`, { method: "POST" });
      await refreshAll("Анкета одобрена");
      renderAdmin();
    } else if (action === "reject-creator") {
      await api(`/api/admin/creators/${button.dataset.id}/reject`, { method: "POST" });
      await refreshAll("Анкета отклонена");
      renderAdmin();
    }
  } catch (error) {
    toast(error.message);
  }
});

document.addEventListener("change", async (event) => {
  const input = event.target.closest('input[type="file"][data-action="deliver-order"]');
  if (!input || !input.files.length) return;
  const form = new FormData();
  form.set("media", input.files[0]);
  try {
    await apiForm(`/api/creator/orders/${input.dataset.id}/deliver`, form);
    await refreshAll("Видео отправлено");
  } catch (error) {
    toast(error.message);
  }
});

bootstrap();
