from whitenoise.storage import CompressedManifestStaticFilesStorage


class StaticConVersiones(CompressedManifestStaticFilesStorage):
    """
    Igual que el de siempre (nombres con hash + comprimidos), pero también
    pone el hash en los `import` entre módulos JS (./ui.js → ./ui.<hash>.js).

    Sin esto, pos.<hash>.js cargaba ./ui.js, ./carrito.js… sin versión, y
    nginx los sirve sin Cache-Control: el navegador podía quedarse con
    módulos viejos y mezclarlos con nuevos, y el POS dejaba de cargar.
    """
    support_js_module_import_aggregation = True
