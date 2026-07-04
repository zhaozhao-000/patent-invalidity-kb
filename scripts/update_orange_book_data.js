const fs = require("fs");
const path = require("path");
const https = require("https");
const childProcess = require("child_process");

const root = path.resolve(__dirname, "..");
const outDir = path.join(root, "data", "external", "orange_book");
const defaultUrl = "https://www.fda.gov/media/76860/download";
const sourceUrl = process.env.ORANGE_BOOK_URL || defaultUrl;

function download(url) {
  return new Promise((resolve, reject) => {
    https
      .get(url, (response) => {
        if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
          resolve(download(response.headers.location));
          return;
        }
        if (response.statusCode !== 200) {
          reject(new Error(`HTTP ${response.statusCode} downloading Orange Book data`));
          return;
        }
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => resolve(Buffer.concat(chunks)));
      })
      .on("error", reject);
  });
}

function parseProducts(text) {
  const lines = text.split(/\r?\n/).filter(Boolean);
  const header = lines.shift();
  if (!header) return [];
  const columns = header.split("~").map((item) => item.trim());
  return lines.map((line) => {
    const values = line.split("~");
    return Object.fromEntries(columns.map((column, index) => [column, values[index] || ""]));
  });
}

function extractZip(zipPath, targetDir) {
  fs.rmSync(targetDir, { recursive: true, force: true });
  fs.mkdirSync(targetDir, { recursive: true });
  if (process.platform === "win32") {
    childProcess.execFileSync("powershell.exe", [
      "-NoProfile",
      "-Command",
      `Expand-Archive -LiteralPath '${zipPath.replaceAll("'", "''")}' -DestinationPath '${targetDir.replaceAll("'", "''")}' -Force`,
    ]);
    return;
  }
  childProcess.execFileSync("unzip", ["-o", zipPath, "-d", targetDir], { stdio: "ignore" });
}

function findFile(dir, pattern) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      const nested = findFile(full, pattern);
      if (nested) return nested;
    } else if (pattern.test(entry.name)) {
      return full;
    }
  }
  return "";
}

async function main() {
  fs.mkdirSync(outDir, { recursive: true });
  const archive = await download(sourceUrl);
  const zipPath = path.join(outDir, "orangebook.zip");
  fs.writeFileSync(zipPath, archive);

  const extractDir = path.join(outDir, "raw");
  extractZip(zipPath, extractDir);
  const productsPath = findFile(extractDir, /^products\.txt$/i);
  const patentsPath = findFile(extractDir, /^patent\.txt$/i);
  if (productsPath) {
    fs.writeFileSync(
      path.join(outDir, "products.json"),
      JSON.stringify(parseProducts(fs.readFileSync(productsPath, "utf8")), null, 2)
    );
  }
  if (patentsPath) {
    fs.copyFileSync(patentsPath, path.join(outDir, "patent.txt"));
  }
  console.log(`Wrote Orange Book data under ${outDir}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
