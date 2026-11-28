package io.github.sirmeili.filamenttracker

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test
import org.w3c.dom.Element
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

// The Keystore key cannot move to another phone, so the app's data stays out of Android backup:
// allowBackup="false" for Android 11 and older, and data extraction rules that exclude it from
// both cloud backup and device-to-device transfer for Android 12 and later (#113).
class BackupRulesTest {
    private val androidNs = "http://schemas.android.com/apk/res/android"

    // Where the app keeps data: SecureStore's SharedPreferences, and the WebView's data under
    // the app's own folders.
    private val appDomains = setOf("root", "file", "database", "sharedpref", "external")

    private fun parse(file: File): Element =
        DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }
            .newDocumentBuilder().parse(file).documentElement

    private fun application(): Element {
        val path = System.getProperty("mergedManifest")
        assertNotNull("the mergedManifest system property (app/build.gradle)", path)
        return parse(File(path)).getElementsByTagName("application").item(0) as Element
    }

    private fun rules(): Element {
        val name = application().getAttributeNS(androidNs, "dataExtractionRules")
        assertEquals("@xml/data_extraction_rules", name)
        return parse(File("src/main/res/xml/data_extraction_rules.xml"))
    }

    private fun excludedDomains(rules: Element, section: String): Set<String> {
        val sections = rules.getElementsByTagName(section)
        assertEquals("one <$section>", 1, sections.length)
        val element = sections.item(0) as Element
        assertEquals("no <include> in <$section>", 0, element.getElementsByTagName("include").length)
        val excludes = element.getElementsByTagName("exclude")
        return (0 until excludes.length)
            .map { excludes.item(it) as Element }
            .filter { it.getAttribute("path") == "." }
            .map { it.getAttribute("domain") }
            .toSet()
    }

    @Test
    fun backupStaysOffForAndroid11AndOlder() {
        assertEquals("false", application().getAttributeNS(androidNs, "allowBackup"))
    }

    @Test
    fun theAppsDataIsLeftOutOfCloudBackup() {
        assertEquals(appDomains, excludedDomains(rules(), "cloud-backup"))
    }

    @Test
    fun theAppsDataIsLeftOutOfDeviceTransfer() {
        assertEquals(appDomains, excludedDomains(rules(), "device-transfer"))
    }
}
