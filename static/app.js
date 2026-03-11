const statusText = document.getElementById("status-text");
const tableBody = document.getElementById("file-table-body");
const emptyState = document.getElementById("empty-state");
const refreshButton = document.getElementById("refresh-btn");
const themeToggleButton = document.getElementById("theme-toggle");
const THEME_STORAGE_KEY = "file-share-theme";

function formatBytes(size) {
    if (size === 0) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    const base = Math.floor(Math.log(size) / Math.log(1024));
    const value = size / 1024 ** base;
    return `${value.toFixed(value >= 10 || base === 0 ? 0 : 1)} ${units[base]}`;
}

function formatDate(isoValue) {
    const dt = new Date(isoValue);
    if (Number.isNaN(dt.getTime())) {
        return "Không rõ";
    }
    return dt.toLocaleString("vi-VN", {
        dateStyle: "short",
        timeStyle: "short",
    });
}

function escapeHtml(input) {
    const div = document.createElement("div");
    div.textContent = input;
    return div.innerHTML;
}

function renderRows(files) {
    tableBody.innerHTML = "";
    if (files.length === 0) {
        emptyState.hidden = false;
        return;
    }

    emptyState.hidden = true;
    for (const file of files) {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td><code>${escapeHtml(file.name)}</code></td>
            <td>${formatBytes(file.size_bytes)}</td>
            <td>${formatDate(file.updated_at)}</td>
            <td>${file.download_count}</td>
            <td><a class="download-link" href="${file.download_url}">Tải file</a></td>
        `;
        tableBody.appendChild(row);
    }
}

async function loadFiles() {
    statusText.textContent = "Đang đồng bộ...";
    try {
        const response = await fetch("/api/files", { method: "GET" });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.detail || "Không thể tải danh sách file.");
        }

        const files = payload.files || [];
        renderRows(files);
        statusText.textContent = `Đã cập nhật lúc ${new Date().toLocaleTimeString("vi-VN")}`;
    } catch (error) {
        statusText.textContent = "Lỗi tải dữ liệu";
        console.error(error);
    }
}

function applyTheme(theme) {
    const isDark = theme === "dark";
    document.body.classList.toggle("dark", isDark);

    if (themeToggleButton) {
        themeToggleButton.textContent = isDark ? "☀️ Sáng" : "🌙 Tối";
        themeToggleButton.setAttribute("aria-pressed", String(isDark));
    }
}

function loadTheme() {
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
    if (savedTheme === "dark" || savedTheme === "light") {
        applyTheme(savedTheme);
        return;
    }

    const preferDark =
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(preferDark ? "dark" : "light");
}

if (refreshButton) {
    refreshButton.addEventListener("click", () => {
        loadFiles();
    });
}

if (themeToggleButton) {
    themeToggleButton.addEventListener("click", () => {
        const nextTheme = document.body.classList.contains("dark")
            ? "light"
            : "dark";
        applyTheme(nextTheme);
        localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    });
}

loadTheme();
renderRows(window.__INITIAL_FILES__ || []);
loadFiles();
setInterval(loadFiles, 30000);
