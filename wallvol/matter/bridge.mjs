// Local Matter controller for the wallvol prototype.
//
// Joins Matter devices (plugs, lights, dimmers) as an additional controller
// ("multi-admin": Apple Home keeps working) using a pairing code from the
// Home app, then switches and dims them. The Python Matter driver talks to it
// over HTTP on 127.0.0.1 only.
//
//   POST /commission {code, label}       -> {nodeId, productName, endpoints:[{number, onOff, level}]}
//   GET  /state?node=ID&ep=N             -> {connected, on, level}   (level 0-100, null if not dimmable)
//   POST /set {node, ep, on?, level?}    -> {ok}
//   GET  /nodes                          -> [{nodeId, productName}]
//
// Env: WALLVOL_MATTER_STORAGE (fabric + keys), WALLVOL_MATTER_PORT (default 5541),
// WALLVOL_MATTER_SECRET (per-launch secret from server.py; requests must carry it).

import http from "node:http";
import { timingSafeEqual } from "node:crypto";
import { Environment, Logger, LogLevel } from "@matter/main";
import { BasicInformationCluster, GeneralCommissioning, LevelControl, OnOff } from "@matter/main/clusters";
import { ManualPairingCodeCodec, NodeId } from "@matter/main/types";
import { CommissioningController } from "@project-chip/matter.js";

Logger.level = LogLevel.WARN;

// Exit when the wallvol server that started us goes away (it holds our stdin)
process.stdin.on("end", () => process.exit(0));
process.stdin.resume();
const environment = Environment.default;
if (process.env.WALLVOL_MATTER_STORAGE) environment.vars.set("storage.path", process.env.WALLVOL_MATTER_STORAGE);
const PORT = Number(process.env.WALLVOL_MATTER_PORT || 5541);

const controller = new CommissioningController({
    environment: { environment, id: "wallvol" },
    autoConnect: false,
    adminFabricLabel: "Wall Volume Panel",
});
await controller.start();

const connected = new Map();   // nodeId string -> PairedNode

async function getNode(id) {
    let node = connected.get(id);
    if (!node) {
        node = await controller.getNode(NodeId(BigInt(id)));
        if (!node.isConnected) node.connect();
        if (!node.initialized) await node.events.initialized;
        connected.set(id, node);
    }
    return node;
}

function endpointOf(node, ep) {
    const devices = node.getDevices();
    return devices.find(d => d.number === ep) ?? devices[0];
}

function describeEndpoints(node) {
    return node.getDevices().map(d => ({
        number: d.number,
        onOff: d.getClusterClient(OnOff.Complete) !== undefined,
        level: d.getClusterClient(LevelControl.Complete) !== undefined,
    })).filter(e => e.onOff || e.level);
}

async function productName(node) {
    try { return await node.getRootClusterClient(BasicInformationCluster)?.getProductNameAttribute(); }
    catch { return undefined; }
}

const routes = {
    async "POST /commission"({ code }) {
        const parsed = ManualPairingCodeCodec.decode(String(code).replace(/[^0-9]/g, ""));
        const nodeId = await controller.commissionNode({
            commissioning: {
                regulatoryLocation: GeneralCommissioning.RegulatoryLocationType.IndoorOutdoor,
                regulatoryCountryCode: "XX",
            },
            discovery: { identifierData: { shortDiscriminator: parsed.shortDiscriminator }, discoveryCapabilities: { onIpNetwork: true } },
            passcode: parsed.passcode,
        });
        const id = String(nodeId);
        const node = await getNode(id);
        return { nodeId: id, productName: await productName(node), endpoints: describeEndpoints(node) };
    },

    async "GET /nodes"() {
        return controller.getCommissionedNodes().map(n => ({ nodeId: String(n) }));
    },

    async "GET /state"(_, q) {
        const node = await getNode(q.get("node"));
        const dev = endpointOf(node, Number(q.get("ep") || 1));
        const onOff = dev.getClusterClient(OnOff.Complete);
        const level = dev.getClusterClient(LevelControl.Complete);
        const on = onOff ? await onOff.getOnOffAttribute() : true;
        let pct = null;
        if (level) {
            const raw = await level.getCurrentLevelAttribute();
            pct = raw === null ? null : Math.round(raw / 254 * 100);
        }
        return { connected: node.isConnected, on, level: pct };
    },

    async "POST /set"({ node: id, ep, on, level }) {
        const node = await getNode(String(id));
        const dev = endpointOf(node, Number(ep || 1));
        const onOff = dev.getClusterClient(OnOff.Complete);
        const lc = dev.getClusterClient(LevelControl.Complete);
        if (level !== undefined && level !== null && lc) {
            if (level <= 0) await onOff?.off();
            else await lc.moveToLevelWithOnOff({
                level: Math.max(1, Math.min(254, Math.round(level / 100 * 254))),
                transitionTime: null, optionsMask: {}, optionsOverride: {},
            });
        } else if (on !== undefined && onOff) {
            await (on ? onOff.on() : onOff.off());
        }
        return { ok: true };
    },
};

// Only the wallvol server may drive devices: right Host (no DNS rebinding) and the
// per-launch secret (no other process or web page can call it)
const SECRET = Buffer.from(process.env.WALLVOL_MATTER_SECRET || "");
const HOSTS = new Set([`127.0.0.1:${PORT}`, `localhost:${PORT}`]);
function allowed(req) {
    const got = Buffer.from(String(req.headers["x-wallvol-secret"] || ""));
    return HOSTS.has(String(req.headers.host || "").toLowerCase())
        && SECRET.length > 0 && got.length === SECRET.length && timingSafeEqual(got, SECRET);
}

http.createServer(async (req, res) => {
    const url = new URL(req.url, "http://localhost");
    if (!allowed(req)) { res.writeHead(403, { "Content-Type": "application/json" }); res.end('{"error":"forbidden"}'); return; }
    const handler = routes[`${req.method} ${url.pathname}`];
    res.setHeader("Content-Type", "application/json");
    if (!handler) { res.writeHead(404); res.end('{"error":"not found"}'); return; }
    let body = "";
    for await (const chunk of req) body += chunk;
    try {
        const out = await handler(body ? JSON.parse(body) : {}, url.searchParams);
        res.end(JSON.stringify(out));
    } catch (e) {
        res.writeHead(500);
        res.end(JSON.stringify({ error: String(e?.message || e) }));
    }
}).listen(PORT, "127.0.0.1", () => console.log(`matter bridge on 127.0.0.1:${PORT}`));
