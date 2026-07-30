export class CodexSecurityError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CodexSecurityError";
  }
}

export class AuthenticationRequiredError extends CodexSecurityError {
  constructor(message: string = "Authentication required. Please configure API key or login via ChatGPT device login.") {
    super(message);
    this.name = "AuthenticationRequiredError";
  }
}

export class ScanCostLimitExceededError extends CodexSecurityError {
  constructor(message: string) {
    super(message);
    this.name = "ScanCostLimitExceededError";
  }
}

export class OutputInsideProtectedRootError extends CodexSecurityError {
  constructor(message: string = "Operation aborted: output directory resides inside the protected repository root.") {
    super(message);
    this.name = "OutputInsideProtectedRootError";
  }
}

export class PluginPythonUnavailableError extends CodexSecurityError {
  constructor(message: string = "Required Python version 3.10+ not found or plugin bundle is corrupt.") {
    super(message);
    this.name = "PluginPythonUnavailableError";
  }
}
