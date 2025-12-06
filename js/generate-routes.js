// public/js/generate-routes.js
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

/**
 * 递归遍历目录并获取所有文件路径
 * @param {string} dir - 目录路径
 * @returns {Array<string>} 文件路径数组
 */
function getAllFiles(dir) {
	let results = [];
	const list = fs.readdirSync(dir);
	// 按字母顺序排序
	list.sort();
	
	list.forEach(file => {
		file = path.resolve(dir, file);
		const stat = fs.statSync(file);
		if (stat && stat.isDirectory()) {
			// 递归遍历子目录
			results = results.concat(getAllFiles(file));
		} else {
			// 只处理tsx文件
			if (file.endsWith('.tsx')) {
				results.push(file);
			}
		}
	});
	
	return results;
}

/**
 * 从文件名提取标题并生成hash
 * @param {string} filePath - 文件路径
 * @returns {Object} 包含title、hash和src_path的对象
 */
function processFileName(filePath) {
	const fileName = path.basename(filePath);
	// 去掉前面 "_数字_" 部分
	const titleWithExtension = fileName.replace(/^_\d+_/, '');
	// 去掉文件扩展名
	const title = titleWithExtension.replace(/\.tsx$/, '');
	
	// 生成hash
	const hash = crypto.createHash('md5').update(title).digest('hex').substring(0, 8);
	
	// 计算相对路径（相对于dev目录）
	const devDir = path.join(__dirname, '..', '../dev');
	const relativePath = path.relative(devDir, filePath);
	
	return {
		title: title,
		hash: hash,
		src_path: relativePath
	};
}

/**
 * 删除文件或文件夹（如果存在）
 * @param {string} targetPath - 目标路径
 */
function removeIfExists(targetPath) {
	if (fs.existsSync(targetPath)) {
		if (fs.statSync(targetPath).isDirectory()) {
			// 递归删除文件夹
			const files = fs.readdirSync(targetPath);
			files.forEach(file => {
				const filePath = path.join(targetPath, file);
				if (fs.statSync(filePath).isDirectory()) {
					removeIfExists(filePath);
				} else {
					fs.unlinkSync(filePath);
				}
			});
			fs.rmdirSync(targetPath);
		} else {
			// 删除文件
			fs.unlinkSync(targetPath);
		}
	}
}

/**
 * 创建目录（如果不存在）
 * @param {string} dirPath - 目录路径
 */
function ensureDirExists(dirPath) {
	if (!fs.existsSync(dirPath)) {
		fs.mkdirSync(dirPath, { recursive: true });
	}
}

/**
 * 复制文件
 * @param {string} src - 源文件路径
 * @param {string} dest - 目标文件路径
 */
function copyFile(src, dest) {
	fs.copyFileSync(src, dest);
}

/**
 * 主函数
 */
function main() {
	const devDir = path.join(__dirname, '..', '../dev');
	const outputFile = path.join(__dirname, 'files.json');
	const appDir = path.join(__dirname, '..', '../app');
	const outDir = path.join(appDir, 'out');
	
	try {
		// 1. 删除 scripts/files.json（如果存在）
		removeIfExists(outputFile);
		console.log('已删除旧的 files.json 文件');
		
		// 2. 删除 /app 中的 /out 文件夹（如果有）
		removeIfExists(outDir);
		console.log('已删除旧的 out 文件夹');
		
		// 3. 创建新的 out 文件夹
		ensureDirExists(outDir);
		console.log('已创建新的 out 文件夹');
		
		// 获取所有文件并排序
		const files = getAllFiles(devDir);
		
		// 处理每个文件名
		const result = files.map(file => {
			return processFileName(file);
		});
		
		// 写入JSON文件
		fs.writeFileSync(outputFile, JSON.stringify(result, null, 2));
		console.log(`成功生成 ${outputFile}，共处理 ${result.length} 个文件`);
		
		// 4. 在 out 文件夹里为每个 hash 创建文件夹，并复制对应的 tsx 文件
		result.forEach(item => {
			const hashDir = path.join(outDir, item.hash);
			ensureDirExists(hashDir);
			
			// 构建源文件路径
			const srcFilePath = path.join(devDir, item.src_path);
			// 构建目标文件路径
			const destFilePath = path.join(hashDir, 'page.tsx');
			
			// 复制文件
			copyFile(srcFilePath, destFilePath);
		});
		
		console.log(`成功创建 ${result.length} 个 hash 文件夹并复制文件`);
		
	} catch (error) {
		console.error('处理文件时出错:', error);
	}
}

// 执行主函数
main();
