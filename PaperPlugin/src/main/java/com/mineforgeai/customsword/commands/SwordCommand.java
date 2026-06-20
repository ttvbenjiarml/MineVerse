package com.mineforgeai.customsword.commands;

import com.mineforgeai.customsword.items.SwordFactory;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

public final class SwordCommand implements CommandExecutor {
    private final SwordFactory swordFactory;

    public SwordCommand(SwordFactory swordFactory) {
        this.swordFactory = swordFactory;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player)) {
            sender.sendMessage("Only players can use this command.");
            return true;
        }
        Player player = (Player) sender;
        player.getInventory().addItem(swordFactory.createSword());
        player.sendMessage("You received the Omniverse Blade.");
        return true;
    }
}
