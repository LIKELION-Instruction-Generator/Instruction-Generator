import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { LoadingState } from "../components/feedback/AsyncState";

export function HomeRedirectPage() {
  const navigate = useNavigate();

  useEffect(() => {
    navigate("/weeks/1/hub", { replace: true });
  }, [navigate]);

  return <LoadingState label="Loading accepted week 1 weekly bundle..." />;
}
