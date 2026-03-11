import { Sidebar } from "../components/Sidebar";
import { MainPanel } from "../components/MainPanel";

export function DashboardPage() {
  return (
    <>
      <div className="flex flex-1 flex-col overflow-hidden">
        <MainPanel />
      </div>
      <Sidebar />
    </>
  );
}
