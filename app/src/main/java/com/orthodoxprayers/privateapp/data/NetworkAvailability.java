package com.orthodoxprayers.privateapp.data;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkInfo;
import android.os.Build;

/** Lightweight connectivity hint. The signed HTTPS request remains the source of truth. */
public final class NetworkAvailability {
    private NetworkAvailability() {}

    public static boolean hasConnectedNetwork(Context context) {
        if (context == null) return true;
        try {
            ConnectivityManager manager = (ConnectivityManager)
                    context.getSystemService(Context.CONNECTIVITY_SERVICE);
            if (manager == null) return true;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                Network network = manager.getActiveNetwork();
                if (network == null) return false;
                NetworkCapabilities capabilities = manager.getNetworkCapabilities(network);
                return capabilities != null
                        && capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
            }
            @SuppressWarnings("deprecation")
            NetworkInfo info = manager.getActiveNetworkInfo();
            return info != null && info.isConnected();
        } catch (SecurityException ignored) {
            // ACCESS_NETWORK_STATE is declared, but never block a signed download if an OEM
            // denies the hint unexpectedly.
            return true;
        }
    }
}
