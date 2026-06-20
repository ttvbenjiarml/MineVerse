package com.mineforgeai.customsword.listeners;

import com.mineforgeai.customsword.items.SwordFactory;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.plugin.java.JavaPlugin;

public final class SwordListener implements Listener {
    private final JavaPlugin plugin;
    private final SwordFactory swordFactory;

    public SwordListener(JavaPlugin plugin, SwordFactory swordFactory) {
        this.plugin = plugin;
        this.swordFactory = swordFactory;
    }

    @EventHandler
    public void onHit(EntityDamageByEntityEvent event) {
        Entity damager = event.getDamager();
        Entity target = event.getEntity();
        if (!(damager instanceof Player) || !(target instanceof LivingEntity)) {
            return;
        }
        Player player = (Player) damager;
        LivingEntity entity = (LivingEntity) target;
        ItemStack item = player.getInventory().getItemInMainHand();
        if (!swordFactory.isCustomSword(item)) {
            return;
        }
        entity.getWorld().spawnParticle(Particle.END_ROD, entity.getLocation().add(0, 1, 0), 20, 0.3, 0.4, 0.3, 0.03);
        entity.getWorld().playSound(entity.getLocation(), Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1.0f, 1.2f);
        player.setCooldown(item.getType(), plugin.getConfig().getInt("cooldown-seconds", 5) * 20);
    }

    @EventHandler
    public void onRightClick(PlayerInteractEvent event) {
        ItemStack item = event.getItem();
        if (!swordFactory.isCustomSword(item)) {
            return;
        }
        Player player = event.getPlayer();
        player.getWorld().spawnParticle(Particle.SOUL_FIRE_FLAME, player.getLocation().add(0, 1, 0), 30, 0.5, 0.5, 0.5, 0.02);
        player.getWorld().playSound(player.getLocation(), Sound.ENTITY_LIGHTNING_BOLT_THUNDER, 0.5f, 1.7f);
    }
}
