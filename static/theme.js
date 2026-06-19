/* CardWatcher manual dark-mode toggle.
 * Loaded synchronously in <head> so the saved theme is applied before first
 * paint (no flash). Choice is remembered in localStorage. */
(function () {
	try {
		if (localStorage.getItem('cw-theme') === 'dark') {
			document.documentElement.classList.add('dark');
		}
	} catch (e) {}
})();

function cwApplyThemeBtn() {
	var dark = document.documentElement.classList.contains('dark');
	document.querySelectorAll('.cw-theme-btn').forEach(function (b) {
		b.textContent = dark ? '☀' : '☾';            // ☀ / ☾
		b.title = dark ? 'Switch to light mode' : 'Switch to dark mode';
	});
}

function cwToggleTheme() {
	var dark = document.documentElement.classList.toggle('dark');
	try { localStorage.setItem('cw-theme', dark ? 'dark' : 'light'); } catch (e) {}
	cwApplyThemeBtn();
	if (typeof window.cwOnThemeChange === 'function') window.cwOnThemeChange();
}

// Colors for Chart.js, theme-aware.
function cwChartColors() {
	var d = document.documentElement.classList.contains('dark');
	return {
		grid: d ? 'rgba(255,255,255,0.10)' : 'rgba(0,0,0,0.10)',
		tick: d ? '#c2c9d1' : '#666'
	};
}

document.addEventListener('DOMContentLoaded', cwApplyThemeBtn);
