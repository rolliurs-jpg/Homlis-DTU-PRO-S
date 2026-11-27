package fr.boitenoirehoymiles.test;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.view.ViewGroup;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Toast;
import android.widget.TextView;
import android.view.View;
import android.net.Uri;

public class MainActivity extends Activity {
    private WebView web;
    private String origin;
    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(7,19,33));
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                            insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        LinearLayout toolbar = new LinearLayout(this); toolbar.setOrientation(LinearLayout.HORIZONTAL);
        Button settings = new Button(this); settings.setText("Adresse du Raspberry"); settings.setAllCaps(false);
        Button reload = new Button(this); reload.setText("Actualiser"); reload.setAllCaps(false);
        toolbar.addView(settings, new LinearLayout.LayoutParams(0, -2, 2));
        toolbar.addView(reload, new LinearLayout.LayoutParams(0, -2, 1));
        root.addView(toolbar, new LinearLayout.LayoutParams(-1, -2));
        TextView loading = new TextView(this); loading.setText("Chargement du tableau…");
        loading.setTextColor(Color.WHITE); loading.setPadding(16, 10, 16, 10); loading.setVisibility(View.GONE);
        root.addView(loading, new LinearLayout.LayoutParams(-1, -2));
        web = new WebView(this); web.setBackgroundColor(Color.rgb(6,17,31));
        web.setWebChromeClient(new WebChromeClient());
        web.getSettings().setJavaScriptEnabled(true); web.getSettings().setDomStorageEnabled(true);
        web.getSettings().setUseWideViewPort(true); web.getSettings().setLoadWithOverviewMode(false);
        web.getSettings().setCacheMode(android.webkit.WebSettings.LOAD_NO_CACHE);
        web.setWebViewClient(new WebViewClient() {
            @Override public void onPageStarted(WebView view, String url, Bitmap icon) { loading.setVisibility(View.VISIBLE); }
            @Override public void onPageFinished(WebView view, String url) { loading.setVisibility(View.GONE); }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                if (origin != null && origin.equals(u.getScheme()+"://"+u.getAuthority())) return false;
                Toast.makeText(MainActivity.this, "Lien externe non ouvert dans cette version de test", Toast.LENGTH_LONG).show(); return true;
            }
        });
        root.addView(web, new LinearLayout.LayoutParams(-1, 0, 1)); setContentView(root);
        settings.setOnClickListener(v -> prompt());
        reload.setOnClickListener(v -> { if (web.getUrl() != null) web.reload(); else prompt(); });
        String saved = getPreferences(MODE_PRIVATE).getString("url", "");
        if (saved.isEmpty()) prompt(); else open(saved);
    }
    private void prompt() {
        EditText input = new EditText(this); input.setSingleLine(true);
        input.setHint("http://adresse-de-votre-raspberry:8765"); input.setText(getPreferences(MODE_PRIVATE).getString("url", ""));
        new AlertDialog.Builder(this).setTitle("Adresse du tableau solaire")
          .setMessage("Entrez l’adresse de votre propre Raspberry, en Wi-Fi local ou via votre VPN privé. Cette application affiche les commandes réelles de votre installation.")
          .setView(input).setPositiveButton("Ouvrir", (d,w)->open(input.getText().toString().trim()))
          .setNegativeButton("Annuler", (d,w)->{}).show();
    }
    private void open(String value) {
        Uri u=Uri.parse(value); String scheme=u.getScheme();
        if (u.getHost()==null || !("http".equals(scheme)||"https".equals(scheme)) || u.getUserInfo()!=null) {
            Toast.makeText(this,"Adresse invalide : utilisez http:// ou https://",Toast.LENGTH_LONG).show(); prompt(); return;
        }
        origin=scheme+"://"+u.getAuthority(); getPreferences(MODE_PRIVATE).edit().putString("url",value).apply(); web.loadUrl(value);
    }
    @Override public void onBackPressed() { if(web.canGoBack()) web.goBack(); else super.onBackPressed(); }
}
