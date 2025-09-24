import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { findPythonEnvsWithJac, clearEnvironmentCache, isCacheValid } from '../utils/envDetection';

export class EnvManager {
    private context: vscode.ExtensionContext;
    private statusBar: vscode.StatusBarItem;
    private jacPath: string | undefined;
    private isScanning: boolean = false;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
        this.statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
        this.statusBar.command = 'jaclang-extension.selectEnv';
        context.subscriptions.push(this.statusBar);
    }

    async init() {
        this.jacPath = this.context.globalState.get<string>('jacEnvPath');
        if (!this.jacPath) {
            await this.promptEnvironmentSelection();
        }
        this.updateStatusBar();
    }

    getJacPath(): string {
        if (this.jacPath) return this.jacPath;
        // Fallback: try to find jac in PATH
        return process.platform === 'win32' ? 'jac.exe' : 'jac';
    }

    async promptInterpreterPath() {
        const currentPath = this.getJacPath();
        
        // Simplified: Just show file browser, no manual typing option
        const fileUri = await vscode.window.showOpenDialog({
            canSelectFiles: true,
            canSelectFolders: false,
            canSelectMany: false,
            openLabel: "Select Jac Executable",
            title: "Select Jac Interpreter",
            filters: process.platform === 'win32' ? {
                'Executable Files': ['exe', 'bat', 'cmd'],
                'All Files': ['*']
            } : {
                'All Files': ['*']
            },
            defaultUri: currentPath && currentPath !== 'jac' && currentPath !== 'jac.exe' 
                ? vscode.Uri.file(path.dirname(currentPath))
                : undefined
        });

        if (fileUri && fileUri[0]) {
            const selectedPath = fileUri[0].fsPath;
            
            // Comprehensive validation before setting
            const validationResult = await this.validateJacExecutable(selectedPath);
            if (!validationResult.isValid) {
                vscode.window.showErrorMessage(`Invalid Jac executable: ${validationResult.error}`);
                return;
            }

            this.jacPath = selectedPath.trim();
            await this.context.globalState.update('jacEnvPath', selectedPath.trim());
            this.updateStatusBar();
            
            const fileName = path.basename(selectedPath);
            
            vscode.window.showInformationMessage(
                `Jac environment set to: ${fileName}`,
                'Show in Explorer'
            ).then(action => {
                if (action === 'Show in Explorer') {
                    vscode.commands.executeCommand('revealFileInOS', vscode.Uri.file(selectedPath));
                }
            });
            
            // Ask if user wants to reload window to apply changes
            const reloadAction = await vscode.window.showInformationMessage(
                'Reload window to apply the new interpreter setting?',
                'Reload Now',
                'Later'
            );
            
            if (reloadAction === 'Reload Now') {
                vscode.commands.executeCommand("workbench.action.reloadWindow");
            }
        }
    }

    /**
     * Comprehensive validation for Jac executable across platforms
     */
    private async validateJacExecutable(executablePath: string): Promise<{isValid: boolean, error?: string}> {
        try {
            // Check if file exists
            const stats = await fs.promises.stat(executablePath);
            if (!stats.isFile()) {
                return { isValid: false, error: 'Path must point to a file, not a directory' };
            }

            const fileName = path.basename(executablePath).toLowerCase();
            const ext = path.extname(fileName);

            // Platform-specific validation
            if (process.platform === 'win32') {
                // Windows: Accept .exe, .bat, .cmd, or no extension
                const validExts = ['.exe', '.bat', '.cmd', ''];
                if (!validExts.includes(ext)) {
                    return { isValid: false, error: 'On Windows, executable must be .exe, .bat, .cmd, or have no extension' };
                }

                // Check if it's named 'jac' (with valid extension)
                const baseName = path.basename(fileName, ext);
                if (baseName !== 'jac') {
                    return { isValid: false, error: 'Executable must be named "jac" (with appropriate extension)' };
                }
            } else {
                // Unix-like systems (Linux, macOS, WSL)
                
                // Check if file is executable
                try {
                    await fs.promises.access(executablePath, fs.constants.X_OK);
                } catch {
                    return { isValid: false, error: 'File is not executable (missing execute permissions)' };
                }

                // Check if it's named 'jac' (no extension on Unix)
                if (fileName !== 'jac') {
                    return { isValid: false, error: 'Executable must be named "jac"' };
                }
            }

            // Try to execute and check if it responds (optional validation)
            // This is more thorough but might be slow
            try {
                const { spawn } = require('child_process');
                const result = await new Promise<{success: boolean, error?: string}>((resolve) => {
                    const proc = spawn(executablePath, ['--version'], { 
                        timeout: 5000,
                        stdio: ['ignore', 'pipe', 'pipe']
                    });
                    
                    let stdout = '';
                    let stderr = '';
                    
                    proc.stdout?.on('data', (data: Buffer) => {
                        stdout += data.toString();
                    });
                    
                    proc.stderr?.on('data', (data: Buffer) => {
                        stderr += data.toString();
                    });
                    
                    proc.on('close', (code) => {
                        if (code === 0 || stdout.toLowerCase().includes('jac')) {
                            resolve({ success: true });
                        } else {
                            resolve({ success: false, error: `Executable test failed: ${stderr || 'Unknown error'}` });
                        }
                    });
                    
                    proc.on('error', (err) => {
                        resolve({ success: false, error: `Failed to execute: ${err.message}` });
                    });
                });

                if (!result.success) {
                    return { isValid: false, error: result.error || 'Executable test failed' };
                }
            } catch (error) {
                // If execution test fails, still accept the file if it passes other checks
                console.warn('Could not test executable, but file passes basic validation:', error);
            }

            return { isValid: true };

        } catch (error: any) {
            if (error.code === 'ENOENT') {
                return { isValid: false, error: 'File does not exist' };
            } else if (error.code === 'EACCES') {
                return { isValid: false, error: 'File is not accessible' };
            } else {
                return { isValid: false, error: `Cannot access file: ${error.message}` };
            }
        }
    }

    async promptEnvironmentSelection(forceRefresh: boolean = false) {
        if (this.isScanning) {
            vscode.window.showInformationMessage('Environment scan already in progress...');
            return;
        }

        this.isScanning = true;
        this.updateStatusBar();

        try {
            const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd();
            
            // Show progress for environment detection
            const envs = await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Discovering Jac environments",
                cancellable: false
            }, async (progress) => {
                if (forceRefresh) {
                    clearEnvironmentCache();
                    progress.report({ message: "Clearing cache and scanning..." });
                } else if (isCacheValid()) {
                    progress.report({ message: "Using cached results..." });
                } else {
                    progress.report({ message: "Scanning for environments..." });
                }
                
                return await findPythonEnvsWithJac(workspaceRoot, !forceRefresh);
            });

            if (envs.length === 0) {
                const action = await vscode.window.showWarningMessage(
                    "No environments with 'jac' executable found.",
                    "Refresh Scan",
                    "Enter interpreter path...",
                    "Cancel"
                );
                if (action === "Refresh Scan") {
                    await this.promptEnvironmentSelection(true);
                } else if (action === "Enter interpreter path...") {
                    await this.promptInterpreterPath();
                }
                return;
            }

            // Organize environments like Python extension
            const condaEnvs: any[] = [];
            const globalEnvs: any[] = [];
            const otherEnvs: any[] = [];

            envs.forEach(env => {
                const envDir = path.dirname(env);
                const envName = path.basename(envDir);
                const envPath = env;
                
                // Create a more descriptive label showing the full path structure
                const getDisplayPath = (fullPath: string) => {
                    const parts = fullPath.split(path.sep);
                    // Show last 3-4 parts of path for better readability
                    if (parts.length > 4) {
                        return '.../' + parts.slice(-3).join('/');
                    }
                    return fullPath;
                };
                
                // Detect conda environments
                if (env.includes('conda') || env.includes('miniconda') || env.includes('anaconda') || env.includes('mambaforge')) {
                    const condaRoot = env.split(path.sep).find(part => 
                        part.includes('conda') || part.includes('miniconda') || 
                        part.includes('anaconda') || part.includes('mambaforge')
                    ) || 'conda';
                    
                    condaEnvs.push({
                        label: `$(symbol-namespace) ${envName}`,
                        description: getDisplayPath(envDir),
                        detail: `Conda environment in ${condaRoot}`,
                        env: envPath,
                        kind: vscode.QuickPickItemKind.Default
                    });
                }
                // Detect global/system environments  
                else if (env.includes('/usr/') || env.includes('/opt/') || env.includes('Program Files') || 
                         envName === 'bin' || env.includes('/usr/local/')) {
                    const systemType = env.includes('Program Files') ? 'Windows System' : 
                                     env.includes('/usr/local/') ? 'User Local' : 
                                     env.includes('/usr/') ? 'System' : 'Global';
                    
                    globalEnvs.push({
                        label: `$(globe) ${systemType}`,
                        description: getDisplayPath(envDir),
                        detail: `System installation: ${envPath}`,
                        env: envPath,
                        kind: vscode.QuickPickItemKind.Default
                    });
                }
                // Everything else (venv, poetry, etc.)
                else {
                    const envType = envDir.includes('.venv') ? 'Virtual Environment' :
                                   envDir.includes('venv') ? 'Virtual Environment' :
                                   envDir.includes('poetry') ? 'Poetry Environment' :
                                   envDir.includes('pyenv') ? 'Pyenv Environment' :
                                   'Environment';
                    
                    otherEnvs.push({
                        label: `$(package) ${envName}`,
                        description: getDisplayPath(envDir),
                        detail: `${envType}: ${envPath}`,
                        env: envPath,
                        kind: vscode.QuickPickItemKind.Default
                    });
                }
            });

            // Build organized quick pick items like Python extension
            const quickPickItems: any[] = [];

            // Add header and action items first
            quickPickItems.push(
                {
                    label: "$(refresh) Refresh",
                    description: "Refresh the list of environments",
                    env: "refresh",
                    kind: vscode.QuickPickItemKind.Default
                },
                {
                    label: "$(folder-opened) Enter interpreter path...",
                    description: "Find and select Jac executable manually",
                    env: "manual",
                    kind: vscode.QuickPickItemKind.Default
                }
            );

            // Add separator and conda environments
            if (condaEnvs.length > 0) {
                quickPickItems.push(
                    { label: "Conda", kind: vscode.QuickPickItemKind.Separator },
                    ...condaEnvs
                );
            }

            // Add separator and global environments  
            if (globalEnvs.length > 0) {
                quickPickItems.push(
                    { label: "Global", kind: vscode.QuickPickItemKind.Separator },
                    ...globalEnvs
                );
            }

            // Add separator and other environments
            if (otherEnvs.length > 0) {
                quickPickItems.push(
                    { label: "Other", kind: vscode.QuickPickItemKind.Separator },
                    ...otherEnvs
                );
            }

            const choice = await vscode.window.showQuickPick(quickPickItems, {
                placeHolder: "Select a Jac interpreter",
                matchOnDescription: true,
                matchOnDetail: true
            });

            if (choice) {
                if (choice.env === "refresh") {
                    await this.promptEnvironmentSelection(true);
                    return;
                }
                
                if (choice.env === "manual") {
                    await this.promptInterpreterPath();
                    return;
                }

                this.jacPath = choice.env;
                await this.context.globalState.update('jacEnvPath', choice.env);
                this.updateStatusBar();
                vscode.window.showInformationMessage(`Jac interpreter set to: ${choice.label.replace(/^\$\([^)]+\)\s*/, '')}`);
                vscode.commands.executeCommand("workbench.action.reloadWindow");
            }
        } catch (error) {
            vscode.window.showErrorMessage(`Error scanning for environments: ${error}`);
        } finally {
            this.isScanning = false;
            this.updateStatusBar();
        }
    }

    // Helper method to get Jac version (you might want to implement this)
    private getJacVersion(jacPath: string): string | null {
        try {
            // This would need to be implemented to actually get version
            // For now, just return a placeholder
            return "Jac";
        } catch {
            return null;
        }
    }

    async refreshEnvironments() {
        await this.promptEnvironmentSelection(true);
    }

    getPythonPath(): string {
        const jacPath = this.getJacPath(); // Use the existing method to get jac's path

        // If jacPath is just 'jac', then python is probably just 'python' in the PATH
        if (jacPath === 'jac' || jacPath === 'jac.exe') {
            return process.platform === 'win32' ? 'python.exe' : 'python';
        }

        // Otherwise, construct the path: C:\path\to\env\Scripts\python.exe
        const dir = path.dirname(jacPath);
        const pythonExe = process.platform === 'win32' ? 'python.exe' : 'python';
        return path.join(dir, pythonExe);
    }

    updateStatusBar() {
        if (this.isScanning) {
            this.statusBar.text = "$(sync~spin) Scanning Jac Envs...";
            this.statusBar.tooltip = "Scanning for Jac environments";
        } else {
            const label = this.jacPath ? path.basename(this.jacPath) : 'No Env';
            const cacheStatus = isCacheValid() ? '$(check)' : '$(refresh)';
            this.statusBar.text = `${cacheStatus} Jac: ${label}`;
            this.statusBar.tooltip = this.jacPath ? 
                `Current: ${this.jacPath}\nClick to change or refresh` : 
                'No Jac environment selected - Click to select';
        }
        this.statusBar.show();
    }
}
