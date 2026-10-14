import SwiftUI

/// Main screen: the Digital Crown sets the target (like the wall knob), the
/// big number is the sauna's current temperature, one button starts or stops.
struct SaunaView: View {
    @ObservedObject var model: SaunaModel
    @State private var crown: Double = 80
    private let red = Color(red: 0.86, green: 0.23, blue: 0.18)

    var body: some View {
        let s = model.state
        let heating = s?.heating ?? false
        VStack(spacing: 4) {
            Text(model.isDemo ? "SAUNA · DEMO" : "SAUNA")
                .font(.system(size: 12, weight: .medium)).tracking(2.5)
                .foregroundStyle(.secondary)

            if let s {
                Text("\(SaunaLimits.f(s.currentC))°")
                    .font(.system(size: 52, weight: .light, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(heating ? red : .primary)
                Text(heating ? "HEATING TO \(SaunaLimits.f(crown))°" : "SET \(SaunaLimits.f(crown))°")
                    .font(.system(size: 13, weight: .medium)).tracking(1.2)
                if !s.doorClosed {
                    Label("Door open", systemImage: "door.left.hand.open")
                        .font(.footnote).foregroundStyle(.orange)
                }
            } else {
                ProgressView()
            }

            Button(heating ? "Stop" : "Start") {
                Task { heating ? await model.stop() : await model.start() }
            }
            .tint(heating ? .gray : red)
            .disabled(model.busy || s == nil || !(s?.online ?? false))

            if let error = model.error {
                Text(error).font(.footnote).foregroundStyle(.orange).multilineTextAlignment(.center)
            }
        }
        .focusable()
        .digitalCrownRotation($crown, from: Double(SaunaLimits.minC), through: Double(SaunaLimits.maxC),
                              by: 1, sensitivity: .medium, isContinuous: false, isHapticFeedbackEnabled: true)
        .onChange(of: crown) { _, value in model.targetC = value }
        .onChange(of: model.targetC) { _, value in if abs(value - crown) >= 1 { crown = value } }
        .task {
            crown = model.targetC
            while !Task.isCancelled {         // poll while the app is on screen
                await model.refresh()
                try? await Task.sleep(for: .seconds(5))
            }
        }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button { model.signOut() } label: { Image(systemName: "rectangle.portrait.and.arrow.right") }
            }
        }
    }
}

/// Sign in with the HUUM app login (stub: typed on the watch; the real app
/// would get it from the iPhone app), or try the demo sauna.
struct SignInView: View {
    @ObservedObject var model: SaunaModel
    @State private var email = ""
    @State private var password = ""

    var body: some View {
        ScrollView {
            VStack(spacing: 8) {
                Text("HUUM SAUNA").font(.system(size: 13, weight: .medium)).tracking(2.5)
                TextField("Email", text: $email).textContentType(.username)
                SecureField("Password", text: $password).textContentType(.password)
                Button(model.busy ? "Signing in…" : "Sign In") {
                    Task { await model.signIn(email: email, password: password) }
                }
                .disabled(email.isEmpty || password.isEmpty || model.busy)
                Button("Try the demo sauna") { model.useDemo() }
                    .font(.footnote)
                if let error = model.error {
                    Text(error).font(.footnote).foregroundStyle(.orange)
                }
            }
        }
    }
}
