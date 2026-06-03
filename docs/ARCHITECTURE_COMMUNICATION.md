# How the Pieces Communicate — Local Metal vs. Cloud Frontend

A common point of confusion: **does the local Metal (on-device GPU inference) talk to the deployed web frontend?**

**Short answer: No.** They live in two different worlds and only ever meet through the **backend API** in the middle. The web frontend and the local Metal **never connect to each other directly**.

---

## Two separate "planes"

```
        ☁️  CLOUD (Modal)                          💻  YOUR MAC (local)
 ┌───────────────────────────┐
 │  Next.js Web Frontend     │  (just a website
 │  (browser UI)             │   in a browser)
 └───────────┬───────────────┘
             │ HTTPS
             ▼
 ┌───────────────────────────┐            ┌──────────────────────────────┐
 │  FastAPI Backend API      │◄──HTTPS────│  MCP Server (daemon)         │
 │  (accounts, catalog,      │            │   + Metal Engine (Apple GPU) │
 │   licenses — source of    │            └──────────────┬───────────────┘
 │   truth)                  │                           │ local socket (MCP)
 └───────────┬───────────────┘                           ▼
             │ calls when NO local Metal       ┌──────────────────────────┐
             ▼                                 │  Your native macOS app   │
 ┌───────────────────────────┐                 │  (uses the SDK)          │
 │  Modal GPU inference app  │                 └──────────────────────────┘
 └───────────────────────────┘
```

The **only thing that crosses** from your Mac to the cloud is HTTPS calls to the **backend API**.

---

## Who talks to whom

| From | To | Over | For |
|---|---|---|---|
| Web frontend (browser) | Backend API | HTTPS | browse, login, acquire license |
| MCP Server (your Mac) | Backend API | HTTPS | **verify license, download weights, send telemetry** |
| Your native app | MCP Server (your Mac) | **local socket** | run inference on the Apple GPU |
| Backend API | Modal GPU | internal | **cloud fallback** inference only |

Notice the MCP server's only cloud contact is the **API** — never the frontend.

---

## Why they can't talk directly

A **browser cannot reach a daemon running on your Mac.** There's no public address for "localhost on someone's laptop," and the browser sandbox forbids it. So:

- **Web Playground** (on the deployed site) → has no way to reach your local Metal → it uses the **Modal cloud GPU**. That is exactly why the cloud fallback exists.
- **A real native macOS app** → talks to the **local MCP daemon over a local socket** → uses **Metal on the Apple GPU**, fully on-device. The cloud is not involved in that inference at all.

---

## Local Metal vs. Modal GPU are *alternatives*, not partners

They never run the same request together. For any inference, it is **one or the other**:

- **Has Apple Silicon + daemon running →** local Metal (fast, private, on-device).
- **No Metal / OOM / daemon down →** the client calls the API's `POST /v1/inference`, which routes to **Modal GPU**.

The **backend API is the shared brain** both planes rely on: it holds accounts, the catalog, and — critically — **licenses**. The local Metal asks the API *"is this user + device licensed for this model?"* before loading it; the frontend asks the same API to issue that license. That license check is the only link between the two planes.

---

## One-line summary

> The web frontend and your local Metal both connect to the **same backend API**, but **not to each other**. Local Metal = on-device inference for native apps; Modal GPU = the cloud stand-in the *website* (and any client without Metal) uses instead.
