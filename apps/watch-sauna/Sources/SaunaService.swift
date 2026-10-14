import Foundation

/// What the watch shows and changes. Temperatures are °C; the UI shows °F.
struct SaunaState: Equatable {
    var heating: Bool
    var currentC: Double
    var targetC: Double?
    var doorClosed: Bool
    var online: Bool
}

enum SaunaError: LocalizedError {
    case signInRejected, doorOpen, offline, http(Int)
    var errorDescription: String? {
        switch self {
        case .signInRejected: return "HUUM rejected the email or password."
        case .doorOpen: return "Close the sauna door to start it."
        case .offline: return "The sauna is offline."
        case .http(let code): return "HUUM error \(code)."
        }
    }
}

/// The sauna, behind an interface so the watch can run against HUUM or a demo.
protocol SaunaService {
    func status() async throws -> SaunaState
    func start(targetC: Int) async throws -> SaunaState
    func stop() async throws -> SaunaState
}

enum SaunaLimits {
    static let minC = 40, maxC = 110      // HUUM UKU range
    static func f(_ c: Double) -> Int { Int((c * 9 / 5 + 32).rounded()) }
}

/// HUUM's cloud API (the one the HUUM app and Home Assistant use):
/// HTTP Basic auth to https://sauna.huum.eu/action/home/{status,start,stop}.
struct HuumService: SaunaService {
    let email: String
    let password: String
    private let base = URL(string: "https://sauna.huum.eu/action/home/")!

    private func call(_ action: String, method: String = "GET", body: [String: Any]? = nil) async throws -> SaunaState {
        var req = URLRequest(url: base.appendingPathComponent(action))
        req.httpMethod = method
        let token = Data("\(email):\(password)".utf8).base64EncodedString()
        req.setValue("Basic \(token)", forHTTPHeaderField: "Authorization")
        if let body {
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let (data, resp) = try await URLSession.shared.data(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if code == 401 || code == 403 { throw SaunaError.signInRejected }
        guard code == 200 else { throw SaunaError.http(code) }
        let json = (try JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        let status = json["statusCode"] as? Int ?? 0
        return SaunaState(
            heating: status == 231,
            currentC: (json["temperature"] as? NSNumber)?.doubleValue ?? 0,
            targetC: (json["targetTemperature"] as? NSNumber)?.doubleValue,
            doorClosed: json["door"] as? Bool ?? false,
            online: status != 230)
    }

    func status() async throws -> SaunaState { try await call("status") }

    func start(targetC: Int) async throws -> SaunaState {
        let now = try await status()
        if !now.online { throw SaunaError.offline }
        if !now.heating && !now.doorClosed { throw SaunaError.doorOpen }   // same rule as the HUUM app
        return try await call("start", method: "POST", body: ["targetTemperature": targetC])
    }

    func stop() async throws -> SaunaState { try await call("stop", method: "POST") }
}

/// A pretend sauna for the simulator and demos: heats about 1 °C every 2 s.
actor DemoSauna: SaunaService {
    private var state = SaunaState(heating: false, currentC: 22, targetC: 80, doorClosed: true, online: true)
    private var last = Date()

    private func tick() {
        let dt = Date().timeIntervalSince(last) / 2
        last = Date()
        let goal = state.heating ? (state.targetC ?? 80) : 22
        let step = min(abs(goal - state.currentC), dt)
        state.currentC += goal > state.currentC ? step : -step
    }

    func status() async throws -> SaunaState { tick(); return state }
    func start(targetC: Int) async throws -> SaunaState {
        tick(); state.heating = true; state.targetC = Double(targetC); return state
    }
    func stop() async throws -> SaunaState { tick(); state.heating = false; return state }
}
