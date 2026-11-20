// The generator, off the page's thread (D-053): loads Pyodide and the package once, then builds plans
// on request. The page can stop this worker if a build takes too long, and nothing else is lost.

let generateJson;

// The package is a plain wheel with the core and `ttg.web`; no dependency is needed (the Typst
// compiler only draws the PDF).
async function load({ pyodideUrl, wheelUrl }) {
  const wheel = fetch(wheelUrl).then((response) => {
    if (!response.ok) throw new Error(`${wheelUrl}: ${response.status}`);
    return response.arrayBuffer();
  });
  const { loadPyodide } = await import(`${pyodideUrl}pyodide.mjs`);
  const pyodide = await loadPyodide({ indexURL: pyodideUrl });
  pyodide.unpackArchive(await wheel, "wheel");
  generateJson = pyodide.pyimport("ttg.web").generate_json;
}

const requests = {
  load,
  generate: ({ form, today }) => generateJson(form, today),
};

// Every request has an id; the answer carries it back, as `result` or as `error`.
self.onmessage = async ({ data }) => {
  try {
    self.postMessage({ id: data.id, result: await requests[data.kind](data) });
  } catch (error) {
    self.postMessage({ id: data.id, error: String(error) });
  }
};
