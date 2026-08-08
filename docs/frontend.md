# SafeGuard AI — Frontend Documentation

## Overview
The SafeGuard AI frontend is a modern, responsive web application built with React and Vite. It provides an intuitive interface for real-time video streaming, static media analysis (images and video files), and reviewing historical safety violations. The application features a premium dark theme, adhering strictly to Material Design 3 (M3) principles.

## Tech Stack
- **Framework:** React 18, Vite
- **Routing:** React Router v6
- **Styling:** Tailwind CSS v4 (using the `@theme` directive for native CSS custom properties)
- **Icons:** Google Material Symbols Outlined
- **HTTP Client:** Axios (for REST API communication)
- **WebSockets:** Native browser WebSocket API (for real-time video streaming)
- **Typography:** Hanken Grotesk (Headings), Inter (Body text), JetBrains Mono (Data & numbers)

## Application Structure
The codebase follows a modular structure located in the `frontend/src` directory:

- `api/client.js`: Defines all API endpoints (Axios instance configured with `/api` proxy).
- `components/layout/`: Contains the primary layout wrappers.
  - `Navbar.jsx`: Top navigation bar containing the YOLOv8 status indicator and notification dropdown.
  - `Sidebar.jsx`: Fixed sidebar for navigation across Dashboard, Violations, Upload, and Settings.
- `components/ui/`: Reusable UI elements.
  - `StatCard.jsx`: Metric display cards used on the Dashboard and Upload pages.
  - `Toggle.jsx`: Custom animated toggle switches used in the Settings page.
- `pages/`: The main views of the application.
  - `DashboardPage.jsx`: The core real-time monitoring view. Connects to a WebSocket for live YOLOv8 frame streaming and displays aggregate daily stats and recent violations.
  - `ViolationsPage.jsx`: A historical data grid of all recorded violations, featuring filtering (by type and time), pagination, and CSV export functionality.
  - `UploadPage.jsx`: Interface for uploading static images or video files. Previews annotated results and bounding box data returned from the backend.
  - `SettingsPage.jsx`: Global configuration page for email alerts, WhatsApp integration, detection thresholds, and PPE requirements.
- `index.css`: The central stylesheet containing Tailwind v4 M3 design tokens, custom animation keyframes, scrollbar styling, and typography utility classes.

## Data Flow & State Management
- **Local State:** Component-level state is managed via React hooks (`useState`, `useEffect`, `useRef`). 
- **Real-Time Feed:** The Dashboard uses a persistent WebSocket connection to `/ws/stream` to receive Base64-encoded JPEG frames processed by the backend YOLOv8 model.
- **REST API:** Standard CRUD operations (fetching stats, violations, updating settings) are handled asynchronously via Axios.

## Design System (M3)
The frontend utilizes a customized Material Design 3 (M3) dark theme:
- **Surface Colors:** Range of dark blues/blacks (`#0b1326`, `#131b2e`, etc.) to create depth.
- **Primary Accent:** Orange (`#ffb693`, `#ff6b00`) used for active states and primary actions.
- **Semantic Colors:** Error (`#ffb4ab`, `#93000a`) for violations, Tertiary/Compliant (`#4edea3`) for positive states.

## Development Commands
- `npm run dev`: Starts the Vite development server (proxies `/api`, `/screenshots`, and `/ws` to the backend on port 8000).
- `npm run build`: Compiles the application for production.
- `npm run lint`: Runs ESLint for code quality checks.
