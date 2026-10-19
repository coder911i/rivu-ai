import http from "k6/http";
import { check, sleep } from "k6";

const api = (__ENV.API_BASE_URL || "http://127.0.0.1:8000/api/v1").replace(/\/+$/, "");
const vus = Number(__ENV.VUS || 10);
const duration = __ENV.DURATION || "1m";

export const options = {
  scenarios: {
    api_baseline: {
      executor: "ramping-vus",
      startVUs: 1,
      stages: [
        { duration: "15s", target: Math.max(1, Math.floor(vus / 2)) },
        { duration, target: vus },
        { duration: "10s", target: 0 },
      ],
      gracefulRampDown: "10s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<750", "p(99)<1500"],
  },
};

export default function () {
  const health = http.get(api.replace(/\/api\/v1$/, "") + "/health", { tags: { endpoint: "health" } });
  check(health, {
    "health endpoint returns 200": (r) => r.status === 200,
    "health response reports healthy": (r) => {
      try { return JSON.parse(r.body).status === "healthy"; } catch (_) { return false; }
    },
  });

  if (__ENV.LOGIN_EMAIL && __ENV.LOGIN_PASSWORD) {
    const login = http.post(
      api + "/auth/login",
      JSON.stringify({ email: __ENV.LOGIN_EMAIL, password: __ENV.LOGIN_PASSWORD }),
      { headers: { "Content-Type": "application/json" }, tags: { endpoint: "login" } },
    );
    check(login, { "login succeeds": (r) => r.status === 200 });
  }
  sleep(1);
}
