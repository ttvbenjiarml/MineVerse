package com.mineforgeai.customsword;

import com.mineforgeai.customsword.commands.SwordCommand;
import com.mineforgeai.customsword.items.SwordFactory;
import com.mineforgeai.customsword.listeners.SwordListener;
import org.bukkit.Bukkit;
import org.bukkit.NamespacedKey;
import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

public final class PaperPluginPlugin extends JavaPlugin {
    private SwordFactory swordFactory;
    private NamespacedKey swordKey;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        swordKey = new NamespacedKey(this, "custom_sword");
        swordFactory = new SwordFactory(this, swordKey);
        Bukkit.getPluginManager().registerEvents(new SwordListener(this, swordFactory), this);
        PluginCommand command = getCommand("givesword");
        if (command != null) {
            command.setExecutor(new SwordCommand(swordFactory));
        }
    }
}
