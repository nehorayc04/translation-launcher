using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using FMT.Core;
using FMT.PluginInterfaces;
using FMT.PluginInterfaces.Assets;
using FMT.ServicesManagers;
using FMT.ServicesManagers.Interfaces;

namespace BF6Plugin;

public class BF6AssetLoader : IAssetLoader
{
	private IFileSystemService fss => SingletonService.GetInstance<IFileSystemService>();

	public void LoadData(global::System.Collections.Generic.IEnumerable<string> superBundles, string folder = "native_data/")
	{
		global::System.Collections.Generic.IEnumerator<string> enumerator = superBundles.GetEnumerator();
		try
		{
			while (((global::System.Collections.IEnumerator)enumerator).MoveNext())
			{
				string current = enumerator.Current;
				string text = folder + current + ".toc";
				string text2 = fss.ResolvePath(text, false, false, "ModData");
				if (!string.IsNullOrEmpty(text2) && File.Exists(text2))
				{
					BF6TOCFile bF6TOCFile = new BF6TOCFile(text, log: true, process: true, modDataPath: false, -1, headerOnly: false);
					((TOCFile)bF6TOCFile).Dispose();
				}
			}
		}
		finally
		{
			((global::System.IDisposable)enumerator)?.Dispose();
		}
	}

	public global::System.Collections.Generic.IEnumerable<IAssetEntry> Load(global::System.Collections.Generic.IEnumerable<string> superBundles)
	{
		//IL_0017: Unknown result type (might be due to invalid IL or missing references)
		fss.TOCFileType = typeof(BF6TOCFile);
		global::System.Collections.Generic.ICollection<string> keys = new FilePathResolvingService().ResolvableNativePaths.Keys;
		global::System.Collections.Generic.IEnumerator<string> enumerator = ((global::System.Collections.Generic.IEnumerable<string>)keys).GetEnumerator();
		try
		{
			while (((global::System.Collections.IEnumerator)enumerator).MoveNext())
			{
				string current = enumerator.Current;
				LoadData(superBundles, current + "/");
			}
		}
		finally
		{
			((global::System.IDisposable)enumerator)?.Dispose();
		}
		return null;
	}
}
