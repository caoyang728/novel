import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// HTML 文档导航请求（浏览器直接访问/刷新页面）回退到 Vite SPA 入口；
// fetch/XHR 请求（Accept: application/json 等）正常代理到 Django
function spaHtmlBypass(req) {
  if (req.headers.accept && req.headers.accept.includes('text/html')) {
    return '/index.html'
  }
}

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // API 与 fetch 请求直连后端；HTML 文档请求（页面导航/刷新）必须回退到 SPA，
      // 否则 /login、/reset-password 等路径会被代理到 Django 返回旧版页面
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/login': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        bypass: spaHtmlBypass,
      },
      '/logout': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        bypass: spaHtmlBypass,
      },
      '/register.html': { target: 'http://localhost:8000', changeOrigin: true },
      '/reset-password': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        bypass: spaHtmlBypass,
      },
      '/admin': { target: 'http://localhost:8000', changeOrigin: true },
      '/static': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ['echarts'],
        },
      },
    },
  },
})
