import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api 로 시작하는 요청은 백엔드(8000번)로 넘긴다.
// 덕분에 화면 코드에서는 서버 주소를 몰라도 되고, CORS 문제도 생기지 않는다.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
