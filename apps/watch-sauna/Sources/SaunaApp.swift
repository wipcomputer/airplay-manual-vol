import SwiftUI

@main
struct SaunaApp: App {
    @StateObject private var model = SaunaModel()

    var body: some Scene {
        WindowGroup {
            if model.service == nil {
                SignInView(model: model)
            } else {
                SaunaView(model: model)
            }
        }
    }
}

/// Holds the sauna state and talks to the service; polls every 5 s while open.
@MainActor
final class SaunaModel: ObservableObject {
    @Published var service: SaunaService?
    @Published var state: SaunaState?
    @Published var targetC: Double = 80
    @Published var error: String?
    @Published var busy = false
    @Published var isDemo = false

    init() {
        // Launch with -demo (e.g. in the simulator) to skip sign-in and use the demo sauna
        if ProcessInfo.processInfo.arguments.contains("-demo") {
            isDemo = true
            service = DemoSauna()
            if ProcessInfo.processInfo.arguments.contains("-heat") {
                Task { [weak self] in await self?.start() }
            }
            return
        }
        if let login = Keychain.load() {
            service = HuumService(email: login.email, password: login.password)
        }
    }

    func signIn(email: String, password: String) async {
        let huum = HuumService(email: email, password: password)
        busy = true
        defer { busy = false }
        do {
            state = try await huum.status()
            Keychain.save(email: email, password: password)
            service = huum
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    func useDemo() {
        isDemo = true
        service = DemoSauna()
    }

    func signOut() {
        Keychain.delete()
        service = nil
        state = nil
        isDemo = false
    }

    func refresh() async {
        guard let service else { return }
        do {
            let s = try await service.status()
            state = s
            if let t = s.targetC, !busy { targetC = t }
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    func start() async { await run { try await $0.start(targetC: Int(self.targetC.rounded())) } }
    func stop() async { await run { try await $0.stop() } }

    private func run(_ action: (SaunaService) async throws -> SaunaState) async {
        guard let service else { return }
        busy = true
        defer { busy = false }
        do { state = try await action(service); error = nil }
        catch { self.error = error.localizedDescription }
    }
}
