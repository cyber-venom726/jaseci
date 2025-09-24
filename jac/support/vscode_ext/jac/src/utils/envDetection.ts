import * as fs from 'fs/promises';
import * as path from 'path';
import * as cp from 'child_process';
import { promisify } from 'util';

const exec = promisify(cp.exec);

// --- Constants for Configuration and Clarity ---
const CACHE_DURATION_MS = 10000; // 10 seconds
const JAC_EXECUTABLE_NIX = 'jac';
const JAC_EXECUTABLE_WIN = 'jac.exe';

const COMMON_VENV_NAMES = ['.venv', 'venv', 'env', '.env', 'virtualenv', 'pyenv'];
const COMMON_PROJECT_DIRS = ['projects', 'workspace', 'dev', 'src'];

// Depth for recursive searches
const WALK_DEPTH_DEFAULT = 3;
const WALK_DEPTH_HOME = 4;
const WALK_DEPTH_VIRTUALENVS = 2;

// --- Cache Management ---
let environmentCache: string[] | null = null;
let lastScanTime: number = 0;

/**
 * Checks if the cache is valid and hasn't expired.
 */
export function isCacheValid(): boolean {
    return environmentCache !== null && (Date.now() - lastScanTime) < CACHE_DURATION_MS;
}

/**
 * Clears the environment cache, forcing a new scan on the next call.
 */
export function clearEnvironmentCache(): void {
    environmentCache = null;
    lastScanTime = 0;
}

/**
 * Checks for a 'jac' executable in a given virtual environment directory.
 * Supports Windows (.exe, .bat, .cmd) and Unix-like systems.
 * @param venvPath The root path of the virtual environment.
 * @returns The full path to the 'jac' executable or null if not found.
 */
async function getJacInVenv(venvPath: string): Promise<string | null> {
    // Unix-like systems (Linux, macOS, WSL)
    const jacPathNix = path.join(venvPath, 'bin', JAC_EXECUTABLE_NIX);
    if (await fileExists(jacPathNix) && await isExecutable(jacPathNix)) {
        return jacPathNix;
    }

    // Windows systems - check multiple possible extensions
    const windowsPaths = [
        path.join(venvPath, 'Scripts', 'jac.exe'),
        path.join(venvPath, 'Scripts', 'jac.bat'),
        path.join(venvPath, 'Scripts', 'jac.cmd'),
        path.join(venvPath, 'Scripts', 'jac'), // Sometimes no extension
    ];

    for (const winPath of windowsPaths) {
        if (await fileExists(winPath)) {
            return winPath;
        }
    }

    return null;
}

/**
 * Asynchronously walks a directory structure to a specified depth looking for venvs with jac.
 * @param baseDir The directory to start from.
 * @param depth The maximum depth to recurse.
 * @returns A promise that resolves to an array of jac executable paths.
 */
async function walkForVenvs(baseDir: string, depth: number): Promise<string[]> {
    if (depth === 0) return [];

    let found: string[] = [];
    let entries: import('fs').Dirent[];

    try {
        entries = await fs.readdir(baseDir, { withFileTypes: true });
    } catch (error) {
        // Silently ignore permission errors, common in deep scans
        return [];
    }

    const promises: Promise<string[] | string | null>[] = entries.map(async (entry) => {
        if (!entry.isDirectory()) return null;

        const fullPath = path.join(baseDir, entry.name);
        const foundJac = await getJacInVenv(fullPath);
        const deeperFinds = walkForVenvs(fullPath, depth - 1); // Recurse deeper

        // Await both results and combine them
        const results = await Promise.all([foundJac, deeperFinds]);
        return results.flat().filter(p => p !== null) as string[];
    });

    const results = await Promise.all(promises);
    return results.flat().filter(p => p !== null) as string[];
}

// --- Discovery Strategies ---

async function findInPath(): Promise<string[]> {
    const pathDirs = process.env.PATH?.split(path.delimiter) || [];
    const found = [];
    
    for (const dir of pathDirs) {
        if (process.platform === 'win32') {
            // Windows: check multiple extensions
            const windowsExes = [
                path.join(dir, 'jac.exe'),
                path.join(dir, 'jac.bat'),
                path.join(dir, 'jac.cmd'),
                path.join(dir, 'jac') // Sometimes no extension
            ];
            
            for (const exe of windowsExes) {
                if (await fileExists(exe)) {
                    found.push(exe);
                    break; // Only add one per directory
                }
            }
        } else {
            // Unix-like systems
            const jacPath = path.join(dir, JAC_EXECUTABLE_NIX);
            if (await fileExists(jacPath) && await isExecutable(jacPath)) {
                found.push(jacPath);
            }
        }
    }
    return found;
}

async function findInCondaEnvs(): Promise<string[]> {
    try {
        const { stdout } = await exec('conda env list', { timeout: 5000 });
        const lines = stdout.split('\n').slice(2); // Skip header lines
        const promises = lines.map(async (line) => {
            const parts = line.trim().split(/\s+/);
            const envPath = parts[parts.length - 1]; // Path is the last part
            if (envPath) {
                return getJacInVenv(envPath);
            }
            return null;
        });
        const results = await Promise.all(promises);
        return results.filter(p => p !== null) as string[];
    } catch (error) {
        // Conda not found or command failed, which is a normal scenario.
        return [];
    }
}

async function findInWorkspace(workspaceRoot: string): Promise<string[]> {
    const searchTasks: Promise<string[]>[] = [];

    // 1. Check common venv names in the root
    for (const dirName of COMMON_VENV_NAMES) {
        searchTasks.push(getJacInVenv(path.join(workspaceRoot, dirName)).then(p => p ? [p] : []));
    }
    
    // 2. Walk common project subdirectories
    for (const projectDir of COMMON_PROJECT_DIRS) {
        const fullPath = path.join(workspaceRoot, projectDir);
        if (await directoryExists(fullPath)) {
            searchTasks.push(walkForVenvs(fullPath, WALK_DEPTH_DEFAULT));
        }
    }

    const results = await Promise.all(searchTasks);
    return results.flat();
}

async function findInHome(workspaceRoot: string): Promise<string[]> {
    const homeDir = process.env.HOME || process.env.USERPROFILE;
    if (!homeDir || homeDir === workspaceRoot) return [];

    const searchTasks: Promise<string[]>[] = [
        walkForVenvs(homeDir, WALK_DEPTH_HOME) // General scan
    ];

    // Specific check for virtualenvwrapper directory
    const venvWrapperDir = path.join(homeDir, '.virtualenvs');
    if (await directoryExists(venvWrapperDir)) {
        searchTasks.push(walkForVenvs(venvWrapperDir, WALK_DEPTH_VIRTUALENVS));
    }
    
    const results = await Promise.all(searchTasks);
    return results.flat();
}


/**
 * Finds all Python environments with the 'jac' executable.
 * Results are cached for 10 seconds to improve performance on subsequent calls.
 *
 * @param workspaceRoot The root directory of the workspace to scan. Defaults to the current working directory.
 * @param useCache Whether to use the cache. Defaults to true.
 * @returns A promise that resolves to a unique array of paths to 'jac' executables.
 */
export async function findPythonEnvsWithJac(workspaceRoot: string = process.cwd(), useCache: boolean = true): Promise<string[]> {
    if (useCache && isCacheValid()) {
        return environmentCache!;
    }

    // Run all discovery strategies in parallel.
    // Promise.allSettled ensures that if one strategy fails (e.g., conda not installed), the others can still succeed.
    const results = await Promise.allSettled([
        findInPath(),
        findInCondaEnvs(),
        findInWorkspace(workspaceRoot),
        findInHome(workspaceRoot)
        // NOTE: WSL discovery is omitted for complexity/robustness but could be added back here.
        // See discussion below for reasons.
    ]);

    const allEnvs: string[] = [];
    for (const result of results) {
        if (result.status === 'fulfilled' && result.value) {
            allEnvs.push(...result.value);
        } else if (result.status === 'rejected') {
            // In a real production app, you might use a proper logger
            console.warn(`A discovery strategy failed:`, result.reason);
        }
    }

    // Deduplicate and cache the results
    const uniqueEnvs = Array.from(new Set(allEnvs));
    environmentCache = uniqueEnvs;
    lastScanTime = Date.now();
    
    return uniqueEnvs;
}

// --- Utility Helpers ---

/**
 * Check if a file has execute permissions (Unix-like systems only)
 */
async function isExecutable(filePath: string): Promise<boolean> {
    if (process.platform === 'win32') {
        return true; // Windows doesn't have execute permissions in the same way
    }
    
    try {
        await fs.access(filePath, fs.constants.X_OK);
        return true;
    } catch {
        return false;
    }
}

async function fileExists(filePath: string): Promise<boolean> {
    try {
        const stat = await fs.stat(filePath);
        return stat.isFile();
    } catch {
        return false;
    }
}

async function directoryExists(dirPath: string): Promise<boolean> {
    try {
        const stat = await fs.stat(dirPath);
        return stat.isDirectory();
    } catch {
        return false;
    }
}