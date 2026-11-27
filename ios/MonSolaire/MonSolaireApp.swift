import SwiftUI
import WebKit

@main
struct MonSolaireApp: App {
    var body: some Scene { WindowGroup { DashboardView() } }
}

struct DashboardView: View {
    @AppStorage("dashboardURL") private var savedURL = ""
    @State private var input = ""
    @State private var showingAddress = false
    @State private var error = ""
    @StateObject private var browser = BrowserModel()

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Button("Adresse du Raspberry") { input = savedURL; showingAddress = true }
                Spacer()
                Button("Démo") { openDemo() }
                Button("Actualiser") { browser.webView.reload() }
            }.padding(12)
            if !error.isEmpty {
                Text(error).foregroundColor(.red).padding(8)
            }
            DashboardBrowser(model: browser, error: $error)
        }
        .onAppear {
            if savedURL.isEmpty { showingAddress = true }
            else { open(savedURL) }
        }
        .alert("Adresse de votre tableau solaire", isPresented: $showingAddress) {
            TextField("http://adresse-de-votre-raspberry:8765", text: $input)
                .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
            Button("Annuler", role: .cancel) { }
            Button("Ouvrir") { open(input) }
        } message: {
            Text("Saisissez l’adresse de votre propre Raspberry, sur votre Wi-Fi ou VPN privé. Le tableau comporte des commandes réelles.")
        }
    }

    private func open(_ text: String) {
        let clean = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: clean), let scheme = url.scheme?.lowercased(),
              ["http", "https"].contains(scheme), url.host != nil,
              url.user == nil, url.password == nil else {
            error = "Adresse invalide : utilisez http:// ou https://."
            return
        }
        error = ""
        savedURL = clean
        browser.origin = "\(scheme)://\(url.host!.lowercased()):\(url.port ?? (scheme == "https" ? 443 : 80))"
        browser.webView.load(URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData))
    }

    private func openDemo() {
        guard let url = Bundle.main.url(forResource: "demo", withExtension: "html") else {
            error = "Démonstration indisponible."
            return
        }
        error = ""
        browser.origin = "demo"
        browser.webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
    }
}

final class BrowserModel: ObservableObject {
    let webView = WKWebView()
    var origin = ""
}

struct DashboardBrowser: UIViewRepresentable {
    @ObservedObject var model: BrowserModel
    @Binding var error: String
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIView(context: Context) -> WKWebView {
        model.webView.navigationDelegate = context.coordinator
        model.webView.uiDelegate = context.coordinator
        return model.webView
    }
    func updateUIView(_ view: WKWebView, context: Context) { context.coordinator.parent = self }

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        var parent: DashboardBrowser
        init(_ parent: DashboardBrowser) { self.parent = parent }
        func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            if parent.model.origin == "demo" {
                decisionHandler(action.request.url?.isFileURL == true ? .allow : .cancel)
                return
            }
            guard let url = action.request.url, let scheme = url.scheme?.lowercased(), let host = url.host?.lowercased() else { decisionHandler(.cancel); return }
            let origin = "\(scheme)://\(host):\(url.port ?? (scheme == "https" ? 443 : 80))"
            decisionHandler(origin == parent.model.origin ? .allow : .cancel)
        }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            parent.error = "Connexion impossible : vérifiez l’adresse, le Wi-Fi ou le VPN."
        }
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { parent.error = "" }
        private func presenter() -> UIViewController? {
            let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
            var current = scenes.flatMap { $0.windows }.first(where: { $0.isKeyWindow })?.rootViewController
            while let presented = current?.presentedViewController { current = presented }
            return current
        }
        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
            guard let host = presenter() else { completionHandler(false); return }
            let dialog = UIAlertController(title: "Confirmation", message: message, preferredStyle: .alert)
            dialog.addAction(UIAlertAction(title: "Annuler", style: .cancel) { _ in completionHandler(false) })
            dialog.addAction(UIAlertAction(title: "Confirmer", style: .default) { _ in completionHandler(true) })
            host.present(dialog, animated: true)
        }
        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
            guard let host = presenter() else { completionHandler(); return }
            let dialog = UIAlertController(title: "Mon solaire", message: message, preferredStyle: .alert)
            dialog.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
            host.present(dialog, animated: true)
        }
    }
}
