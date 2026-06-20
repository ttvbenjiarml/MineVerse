package com.mineforgeai.customsword.items;

import org.bukkit.ChatColor;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.ShapedRecipe;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.java.JavaPlugin;

public final class SwordFactory {
    private final JavaPlugin plugin;
    private final NamespacedKey swordKey;

    public SwordFactory(JavaPlugin plugin, NamespacedKey swordKey) {
        this.plugin = plugin;
        this.swordKey = swordKey;
        registerRecipe();
    }

    public ItemStack createSword() {
        ItemStack sword = new ItemStack(Material.DIAMOND_SWORD);
        ItemMeta meta = sword.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(ChatColor.AQUA + "Omniverse Blade");
            meta.addItemFlags(ItemFlag.HIDE_ATTRIBUTES, ItemFlag.HIDE_ENCHANTS);
            meta.getPersistentDataContainer().set(swordKey, PersistentDataType.BYTE, Byte.valueOf((byte) 1));
            sword.setItemMeta(meta);
        }
        sword.addUnsafeEnchantment(Enchantment.SHARPNESS, 5);
        return sword;
    }

    public boolean isCustomSword(ItemStack stack) {
        if (stack == null || !stack.hasItemMeta()) {
            return false;
        }
        ItemMeta meta = stack.getItemMeta();
        return meta != null && meta.getPersistentDataContainer().has(swordKey, PersistentDataType.BYTE);
    }

    private void registerRecipe() {
        ShapedRecipe recipe = new ShapedRecipe(new NamespacedKey(plugin, "omniverse_blade"), createSword());
        recipe.shape(" ND", " SN", "S  " );
        recipe.setIngredient('N', Material.NETHER_STAR);
        recipe.setIngredient('D', Material.DIAMOND);
        recipe.setIngredient('S', Material.STICK);
        plugin.getServer().addRecipe(recipe);
    }
}
