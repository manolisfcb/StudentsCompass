import { createBrowserRouter, Navigate } from "react-router-dom";

import { SmokePage } from "@/features/smoke/SmokePage";

/**
 * One route for now. The eight verticals of plan 08 §8 register their own
 * routes here as they land; the shells and guards arrive with TASK-044.
 */
export const router = createBrowserRouter([
  { path: "/__smoke", element: <SmokePage /> },
  { path: "*", element: <Navigate to="/__smoke" replace /> },
]);
