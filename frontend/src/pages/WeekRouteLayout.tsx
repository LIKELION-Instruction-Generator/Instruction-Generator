import { Outlet, useParams } from "react-router-dom";
import { ErrorState, LoadingState } from "../components/feedback/AsyncState";
import {
  WeeklyWorkspaceProvider,
  useWeeklyWorkspace,
} from "../providers/weekly-workspace";

function WeekRouteContent() {
  const { bundle, error, loading, refetch } = useWeeklyWorkspace();

  if (loading && !bundle) {
    return <LoadingState label="Loading weekly topic, guide, quiz, and report data..." />;
  }

  if (error && !bundle) {
    return (
      <ErrorState
        description={error}
        onRetry={refetch}
        title="Weekly bundle could not be loaded"
      />
    );
  }

  return <Outlet />;
}

export function WeekRouteLayout() {
  const { weekId } = useParams();
  if (!weekId) {
    return (
      <ErrorState
        description="The route is missing `weekId`."
        title="Unknown weekly route"
      />
    );
  }

  return (
    <WeeklyWorkspaceProvider weekId={weekId}>
      <WeekRouteContent />
    </WeeklyWorkspaceProvider>
  );
}
