import { app } from "../../scripts/app.js";

const NODE_NAME = "VRGDG_MiniMaxStudio";
const BUTTON = "VRGDG MiniMax";

function ensureButton(node) {
  if ((node.widgets || []).some((w) => w?.type === "button" && w?.name === BUTTON)) return;
  // The studio lives in minimax_studio/studio.mjs and is imported on first open so it does not load with every page.
  const button = node.addWidget("button", BUTTON, null, () => {
    import("./minimax_studio/studio.mjs")
      .then(({ openMiniMaxStudio }) => openMiniMaxStudio())
      .catch((error) => window.alert(`VRGDG MiniMax failed to open: ${error.message || error}`));
  });
  button.serialize = false;
  node.size = [Math.max(node.size?.[0] || 240, 240), Math.max(node.size?.[1] || 60, 60)];
}

app.registerExtension({
  name: "vrgdg.MiniMaxStudio",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_NAME) return;
    const onNodeCreated = nodeType.prototype.onNodeCreated;
    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onNodeCreated = function () {
      const result = onNodeCreated?.apply(this, arguments);
      ensureButton(this);
      return result;
    };
    nodeType.prototype.onConfigure = function () {
      const result = onConfigure?.apply(this, arguments);
      ensureButton(this);
      return result;
    };
  },
});
