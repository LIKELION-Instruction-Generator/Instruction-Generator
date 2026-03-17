import { Navigate, createBrowserRouter } from "react-router-dom";
import { HomeRedirectPage } from "../pages/HomeRedirectPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { WeekHubPage } from "../pages/WeekHubPage";
import { WeekQuizPage } from "../pages/WeekQuizPage";
import { WeekReportPage } from "../pages/WeekReportPage";
import { WeekRouteLayout } from "../pages/WeekRouteLayout";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <HomeRedirectPage />,
  },
  {
    path: "/weeks/:weekId",
    element: <WeekRouteLayout />,
    children: [
      {
        index: true,
        element: <Navigate replace to="hub" />,
      },
      {
        path: "hub",
        element: <WeekHubPage />,
      },
      {
        path: "quiz",
        element: <WeekQuizPage />,
      },
      {
        path: "report",
        element: <WeekReportPage />,
      },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);
