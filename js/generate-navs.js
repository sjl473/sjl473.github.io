// public/js/generate-navs.js
const fs = require('fs');
const path = require('path');

/**
 * 读取files.json并创建标题到hash的映射
 * @returns {Map<string, string>} 标题到hash的映射
 */
function createTitleToHashMap() {
	const filesJsonPath = path.join(__dirname, '..', '..', 'public/js', 'files.json');
	const filesData = JSON.parse(fs.readFileSync(filesJsonPath, 'utf8'));
	
	const map = new Map();
	filesData.forEach(item => {
		map.set(item.title, item.hash);
	});
	
	return map;
}

/**
 * 格式化标题，只将下划线转换为空格，保持原有大小写
 * @param {string} title - 原始标题
 * @returns {string} 格式化后的标题
 */
function formatTitle(title) {
	// 只将下划线转换为空格，保持原有大小写格式
	return title.replace(/_/g, ' ');
}

/**
 * 处理名称，移除前缀的 _数字_ 部分
 * @param {string} name - 原始名称
 * @returns {string} 处理后的名称
 */
function processName(name) {
	// 移除前缀的 _数字_ 部分（包括文件夹和文件）
	return name.replace(/^_\d+_/, '');
}

/**
 * 递归构建目录结构
 * @param {string} dirPath - 当前目录路径
 * @param {Map<string, string>} titleToHash - 标题到hash的映射
 * @param {string} basePath - 基础路径
 * @returns {Array<Object>} 导航项数组
 */
function buildDirectoryStructure(dirPath, titleToHash, basePath = '') {
	const items = [];
	const entries = fs.readdirSync(dirPath, { withFileTypes: true });
	
	// 按名称排序
	entries.sort((a, b) => a.name.localeCompare(b.name));
	
	for (const entry of entries) {
		const processedName = processName(entry.name);
		const fullPath = path.join(dirPath, entry.name);
		
		if (entry.isDirectory()) {
			// 处理目录
			const dirTitle = formatTitle(processedName);
			const children = buildDirectoryStructure(fullPath, titleToHash, basePath);
			
			if (children.length > 0) {
				items.push({
					title: dirTitle,
					children: children
				});
			}
		} else if (entry.isFile() && entry.name.endsWith('.tsx')) {
			// 处理tsx文件
			const fileNameWithoutExt = processedName.replace(/\.tsx$/, '');
			const fileTitle = fileNameWithoutExt;
			const hash = titleToHash.get(fileTitle);
			
			if (hash) {
				items.push({
					title: formatTitle(fileTitle),
					path: `/${hash}`
				});
			}
		}
	}
	
	return items;
}

/**
 * 主函数
 */
function main() {
	try {
		// 创建标题到hash的映射
		const titleToHash = createTitleToHashMap();
		
		// 构建导航结构
		const devDir = path.join(__dirname, '..', '..', 'dev');
		const navStructure = buildDirectoryStructure(devDir, titleToHash);
		
		// 生成最终的导航JSON
		const navJson = navStructure;
		
		// 写入文件
		const outputPath = path.join(__dirname, 'navs.json');
		fs.writeFileSync(outputPath, JSON.stringify(navJson, null, 2));
		
		console.log(`导航JSON已生成: ${outputPath}`);
	} catch (error) {
		console.error('生成导航JSON时出错:', error);
	}
}

// 执行主函数
main();
