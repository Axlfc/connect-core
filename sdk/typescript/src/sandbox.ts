import * as path from "path";

export interface SandboxConfig {
  readOnlyRoots: string[];
  writableRoots: string[];
  seccompProfilePath?: string;
  uid?: number;
}

export class SandboxSecurityManager {
  /**
   * Sanitizes environment variables, redacting sensitive credentials and normalizing variables.
   */
  public static sanitizeEnvironment(env: Record<string, string | undefined>): Record<string, string> {
    const sanitized: Record<string, string> = {};
    const sensitiveKeys = [/key/i, /token/i, /secret/i, /password/i, /auth/i];

    for (const [k, v] of Object.entries(env)) {
      if (v === undefined || v === "") {
        continue; // Normalization: empty strings treated as undefined
      }

      const isSensitive = sensitiveKeys.some(regex => regex.test(k));
      if (isSensitive && k !== "OPENAI_API_KEY" && k !== "CODEX_API_KEY") {
        sanitized[k] = "[REDACTED]";
      } else {
        sanitized[k] = v;
      }
    }

    return sanitized;
  }

  /**
   * Generates a Bubblewrap execution command argument list for Linux sandboxing.
   */
  public static generateBwrapArgs(config: SandboxConfig, execCommand: string[]): string[] {
    const args: string[] = ["bwrap", "--unshare-all"];

    for (const ro of config.readOnlyRoots) {
      args.push("--ro-bind", ro, ro);
    }
    for (const rw of config.writableRoots) {
      args.push("--bind", rw, rw);
    }

    if (config.uid) {
      args.push("--uid", config.uid.toString());
    }

    args.push(...execCommand);
    return args;
  }

  /**
   * Returns a standard Seccomp profile JSON for strict syscall limitations.
   */
  public static getSeccompProfile(): Record<string, any> {
    return {
      defaultAction: "SCMP_ACT_ERRNO",
      architectures: ["SCMP_ARCH_X86_64", "SCMP_ARCH_AARCH64"],
      syscalls: [
        {
          name: "read",
          action: "SCMP_ACT_ALLOW"
        },
        {
          name: "write",
          action: "SCMP_ACT_ALLOW"
        },
        {
          name: "exit_group",
          action: "SCMP_ACT_ALLOW"
        }
      ]
    };
  }
}
