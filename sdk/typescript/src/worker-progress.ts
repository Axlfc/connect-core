export interface ScanWorkerStatus {
  workerId: number;
  status: "idle" | "running" | "completed" | "failed";
  currentFile?: string;
  filesProcessed: number;
  totalFiles: number;
}

export class WorkerProgressTracker {
  private workers: Map<number, ScanWorkerStatus> = new Map();

  public updateWorker(workerId: number, update: Partial<ScanWorkerStatus>) {
    const existing = this.workers.get(workerId) || {
      workerId,
      status: "idle",
      filesProcessed: 0,
      totalFiles: 0
    };
    this.workers.set(workerId, { ...existing, ...update });
  }

  public getStatusList(): ScanWorkerStatus[] {
    return Array.from(this.workers.values());
  }

  public printProgressTable() {
    console.clear();
    console.log("=== SCAN WORKERS STATUS ===");
    for (const w of this.workers.values()) {
      console.log(`Worker #${w.workerId} | Status: ${w.status.toUpperCase()} | Processed: ${w.filesProcessed}/${w.totalFiles} | Active: ${w.currentFile || "N/A"}`);
    }
  }
}
