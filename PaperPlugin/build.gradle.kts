plugins { java }

repositories {
    mavenCentral()
    maven("https://repo.papermc.io/repository/maven-public/")
}

dependencies {
    compileOnly("io.papermc.paper:paper-api:${property("paperVersion")}-R0.1-SNAPSHOT")
}

java {
    toolchain.languageVersion.set(JavaLanguageVersion.of(property("projectJavaVersion").toString().toInt()))
}

tasks.withType<JavaCompile>().configureEach {
    options.release.set(property("projectJavaVersion").toString().toInt())
}
