import { createHashRouter, Navigate, Outlet } from "react-router-dom";
import { AppLayout } from "@/components/AppLayout";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { LoginPage } from "@/features/auth/LoginPage";
import { Toaster } from "@/components/ui/toast";
import { ScenesPage } from "@/features/scenes/ScenesPage";
import { SceneDesignerPage } from "@/features/scenes/SceneDesignerPage";
import { BoardsPage } from "@/features/boards/BoardsPage";
import { PipelinesPage } from "@/features/pipelines/PipelinesPage";
import { PipelineEditorPage } from "@/features/pipelines/PipelineEditorPage";

// A hash router is intentional: the API owns top-level paths (/scenes, /boards…),
// so path-based routes would collide with the same-origin backend. Fragments never
// reach the server, so deep-links and refreshes always resolve to the SPA.
function RootLayout() {
  return (
    <>
      <Outlet />
      <Toaster />
    </>
  );
}

export const router = createHashRouter([
  {
    element: <RootLayout />,
    children: [
      { path: "/login", element: <LoginPage /> },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <AppLayout />,
            children: [
              { index: true, element: <Navigate to="/scenes" replace /> },
              { path: "scenes", element: <ScenesPage /> },
              { path: "scenes/:sceneId", element: <SceneDesignerPage /> },
              { path: "boards", element: <BoardsPage /> },
              { path: "pipelines", element: <PipelinesPage /> },
              { path: "pipelines/:pipelineId", element: <PipelineEditorPage /> },
            ],
          },
        ],
      },
    ],
  },
]);
